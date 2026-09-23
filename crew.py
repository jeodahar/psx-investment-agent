import os
import re
import json
import time
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from duckduckgo_search import DDGS
import litellm

load_dotenv()


# --- Compatibility patch -----------------------------------------------
# Newer crewai versions tag messages with an internal "cache_breakpoint"
# key for prompt caching. OpenAI/Anthropic's native paths strip it before
# sending, but the generic LiteLLM path (used for Groq) does not yet, so
# Groq's API rejects the request with a schema validation error. This
# strips the key before every LiteLLM call until that's fixed upstream.
#
# It also retries on Groq's TPM (tokens-per-minute) rate limit instead of
# letting the whole crew run die on a single 429 — Groq's free tier is
# only 8,000 TPM for this model, which a 3-agent pipeline can bump into —
# and paces every call with a minimum gap so we approach that ceiling
# gradually instead of bursting into it.
_original_completion = litellm.completion
_MAX_RATE_LIMIT_RETRIES = 5
_MIN_CALL_INTERVAL_SECONDS = 2.5
_last_call_time = 0.0


def _extract_retry_seconds(message: str) -> float:
    match = re.search(r"try again in\s*([\d.]+)s", message, flags=re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 3.0


def _patched_completion(*args, **kwargs):
    global _last_call_time

    messages = kwargs.get("messages")
    if messages:
        kwargs["messages"] = [
            {k: v for k, v in m.items() if k != "cache_breakpoint"} if isinstance(m, dict) else m
            for m in messages
        ]

    # Proactive pacing: never fire two completions closer together than this,
    # so a burst of agent calls doesn't spike tokens-per-minute all at once.
    elapsed = time.monotonic() - _last_call_time
    if elapsed < _MIN_CALL_INTERVAL_SECONDS:
        time.sleep(_MIN_CALL_INTERVAL_SECONDS - elapsed)

    last_err = None
    for attempt in range(_MAX_RATE_LIMIT_RETRIES):
        try:
            result = _original_completion(*args, **kwargs)
            _last_call_time = time.monotonic()
            return result
        except litellm.RateLimitError as e:
            last_err = e
            wait = _extract_retry_seconds(str(e)) + 0.5
            time.sleep(wait)
    _last_call_time = time.monotonic()
    raise last_err
# -------------------------------------------------------------------------


litellm.completion = _patched_completion
# -------------------------------------------------------------------------


def _ddg_search(query: str, max_results: int = 2) -> str:
    """Shared DuckDuckGo search helper used by both the CrewAI tool and the chat advisor."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"Search failed for query '{query}': {e}"

    if not results:
        return f"No results found for '{query}'."

    formatted = []
    for r in results:
        title = r.get("title", "")
        snippet = (r.get("body", "") or "")[:150]
        url = r.get("href", "")
        formatted.append(f"Title: {title}\nSnippet: {snippet}\nURL: {url}")
    return "\n\n".join(formatted)


class DuckDuckGoSearchTool(BaseTool):
    """Custom DuckDuckGo search tool.

    crewai_tools has dropped/renamed its built-in DuckDuckGoSearchTool across
    versions, so we wrap the `duckduckgo-search` package directly instead of
    depending on crewai_tools for this.
    """
    name: str = "DuckDuckGo Search"
    description: str = (
        "Search the web via DuckDuckGo for a given query. "
        "Input should be a plain search query string. "
        "Returns the top result titles, snippets, and URLs."
    )

    def _run(self, query: str) -> str:
        return _ddg_search(query, max_results=2)


def get_llm(max_tokens: int = 500):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
    # crewai's Agent no longer accepts a LangChain LLM object directly — it
    # wants either a plain model string or crewai's own LLM class, which
    # routes through litellm. The "groq/" prefix tells litellm which provider
    # to use.
    return LLM(
        model="groq/openai/gpt-oss-120b",
        api_key=api_key,
        temperature=0.2,
        max_tokens=max_tokens,
    )


def _build_crew(stock_symbol: str, budget: float, risk_profile: str):
    # Research/technical agents only need short prose summaries; the advisor
    # has to fit the entire structured JSON (summaries + risks + action plan
    # arrays) in one completion, so it gets a bigger token budget or its
    # output gets cut off mid-JSON and fails to parse.
    research_llm = get_llm(max_tokens=350)
    technical_llm = get_llm(max_tokens=350)
    advisor_llm = get_llm(max_tokens=1000)
    search_tool = DuckDuckGoSearchTool()

    researcher = Agent(
        role="Pakistan Stock Exchange Fundamental Analyst",
        goal=f"Gather recent financial fundamentals and news for PSX stock '{stock_symbol}'.",
        backstory=(
            "You are a KSE-100 equity researcher. You pull EPS growth, P/E ratio vs sector average, "
            "dividend yield, debt-to-equity, and any recent material news (results, bonus/dividend "
            "announcements, management changes) for the given stock. You always search PSX-specific "
            "and Pakistani financial news sources (e.g. site:psx.com.pk, Business Recorder, Dawn "
            "Business, Mettis Global) rather than generic global results."
        ),
        tools=[search_tool],
        llm=research_llm,
        max_iter=2,
        verbose=True
    )

    technical_analyst = Agent(
        role="PSX Technical Analyst",
        goal=f"Assess the technical trend and momentum for '{stock_symbol}' (price vs moving averages, RSI, volume).",
        backstory=(
            "You are a chartist who reads recent price action, moving-average positioning, RSI "
            "readings, and volume trends reported in market commentary or trading-view style "
            "write-ups for PSX stocks. If exact indicator values aren't available from search, you "
            "clearly say so and reason from whatever price-trend and volume information you can find, "
            "flagging your confidence as Low, Medium, or High."
        ),
        tools=[search_tool],
        llm=technical_llm,
        max_iter=2,
        verbose=True
    )

    advisor = Agent(
        role="Senior Portfolio Manager",
        goal="Combine fundamental and technical findings into a single, risk-managed, structured verdict.",
        backstory=(
            "You are an SECP-aware portfolio manager. You never guarantee returns. You weigh "
            "fundamentals (60%) and technicals (40%) into a 0-100 conviction score, and you always "
            "size the position and set a stop-loss relative to the investor's stated budget and risk "
            "profile."
        ),
        llm=advisor_llm,
        verbose=True
    )

    research_task = Task(
        description=(
            f"Research PSX stock '{stock_symbol}'. Find: latest EPS/quarterly results, P/E ratio and "
            "how it compares to the sector average, dividend yield and payout history, debt-to-equity, "
            "and any material news in the last 3 months. List concrete numbers where you find them, "
            "and note clearly which figures you could not confirm."
        ),
        expected_output=(
            "A structured fundamentals brief: EPS trend, P/E (stock vs sector), dividend yield, "
            "debt-to-equity, key recent news, and a confidence note on data freshness."
        ),
        agent=researcher
    )

    technical_task = Task(
        description=(
            f"Assess '{stock_symbol}' technically: is price above/below its 200-day trend, what is the "
            "recent RSI/momentum picture, is volume rising or falling, and what does that imply for "
            "near-term entry timing. State your confidence (Low/Medium/High) given the data you found."
        ),
        expected_output="A short technical read: trend direction, momentum state, volume note, confidence level.",
        agent=technical_analyst
    )

    advisory_task = Task(
        description=(
            f"Using the fundamentals brief and technical read for '{stock_symbol}', produce a "
            f"recommendation for an investor with a PKR {budget:,.2f} budget and a "
            f"'{risk_profile}' risk profile. Weigh fundamentals 60% / technicals 40% into a single "
            "0-100 conviction score.\n\n"
            "Keep every field brief so the whole response fits comfortably in one completion: "
            "each summary field must be ONE sentence, and key_risks and action_plan must each have "
            "AT MOST 3 short items.\n\n"
            "Return ONLY a JSON object with these exact keys, no markdown fences, no extra text:\n"
            "{\n"
            '  "symbol": string,\n'
            '  "verdict": "Buy" | "Hold" | "Avoid",\n'
            '  "conviction_score": integer 0-100,\n'
            '  "entry_range_pkr": string,\n'
            '  "stop_loss_pkr": string,\n'
            '  "position_size_pkr": string,\n'
            '  "fundamental_summary": string (1 sentence),\n'
            '  "technical_summary": string (1 sentence),\n'
            '  "key_risks": [string, ...] (max 3 items),\n'
            '  "action_plan": [string, ...] (max 3 items)\n'
            "}"
        ),
        expected_output="A single compact, valid JSON object matching the schema above, and nothing else.",
        agent=advisor,
        context=[research_task, technical_task]
    )

    return Crew(
        agents=[researcher, technical_analyst, advisor],
        tasks=[research_task, technical_task, advisory_task],
        process=Process.sequential,
        verbose=True
    )


def _parse_json_result(raw_result: str, symbol: str) -> dict:
    """Best-effort extraction of the advisor's JSON block, with a safe fallback."""
    text = str(raw_result).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "symbol": symbol,
        "verdict": "Unparsed",
        "conviction_score": None,
        "raw_output": text
    }


def run_psx_analysis(stock_symbol: str, budget: float, risk_profile: str) -> dict:
    """Run the full 3-agent pipeline for a single stock and return a parsed dict."""
    crew = _build_crew(stock_symbol, budget, risk_profile)
    result = crew.kickoff()
    return _parse_json_result(result, stock_symbol)


def compare_stocks(symbols: list, budget: float, risk_profile: str) -> list:
    """Run the pipeline across several candidate tickers and return results
    sorted by conviction score (highest first) for easy ranking."""
    results = []
    per_stock_budget = budget / max(len(symbols), 1)
    for i, sym in enumerate(symbols):
        if i > 0:
            # Give Groq's per-minute token budget some room to recover
            # between stocks, on top of the in-call retry/backoff above.
            time.sleep(12)
        try:
            results.append(run_psx_analysis(sym, per_stock_budget, risk_profile))
        except Exception as e:
            results.append({"symbol": sym, "verdict": "Error", "conviction_score": None, "raw_output": str(e)})

    def _score(r):
        s = r.get("conviction_score")
        return s if isinstance(s, (int, float)) else -1

    return sorted(results, key=_score, reverse=True)


# --- Lightweight chat advisor --------------------------------------------
# A single plain completion (no multi-agent crew) so chatting stays fast and
# cheap on the same Groq free-tier TPM budget. Optionally grounds the answer
# with one DuckDuckGo search of the latest user message.

_CHAT_SYSTEM_PROMPT = (
    "You are a PSX (Pakistan Stock Exchange) investment research assistant. You give "
    "educational, risk-aware guidance: fundamentals, technicals, sector context, "
    "diversification, position sizing, and stop-losses. You are NOT a licensed financial "
    "advisor and you never guarantee returns or issue unconditional buy/sell orders — frame "
    "suggestions as conditional on the investor's own risk tolerance, and tell them to verify "
    "against official PSX filings or a licensed broker before acting. Keep answers concise "
    "and practical, in plain language."
)


def chat_with_advisor(messages: list, use_search: bool = False) -> str:
    """Answer one turn of a chat conversation.

    messages: list of {"role": "user"|"assistant", "content": str}, oldest first.
    use_search: if True, runs one DuckDuckGo search on the latest user message
    and feeds the results in as extra context before answering.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")

    convo = [{"role": "system", "content": _CHAT_SYSTEM_PROMPT}]

    if use_search and messages:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if last_user:
            results = _ddg_search(last_user, max_results=3)
            convo.append({
                "role": "system",
                "content": f"Recent web search results that may help answer the next question:\n\n{results}"
            })

    # Cap history so a long-running chat doesn't blow the per-minute token budget.
    convo.extend(messages[-6:])

    response = litellm.completion(
        model="groq/openai/gpt-oss-120b",
        api_key=api_key,
        temperature=0.3,
        max_tokens=400,
        messages=convo,
    )
    return response["choices"][0]["message"]["content"]
