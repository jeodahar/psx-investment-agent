import os
import re
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from duckduckgo_search import DDGS
from langchain_groq import ChatGroq

load_dotenv()


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
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
        except Exception as e:
            return f"Search failed for query '{query}': {e}"

        if not results:
            return f"No results found for '{query}'."

        formatted = []
        for r in results:
            title = r.get("title", "")
            snippet = r.get("body", "")
            url = r.get("href", "")
            formatted.append(f"Title: {title}\nSnippet: {snippet}\nURL: {url}")
        return "\n\n".join(formatted)


def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
    return ChatGroq(
        temperature=0.2,
        model_name="openai/gpt-oss-120b",
        groq_api_key=api_key
    )


def _build_crew(stock_symbol: str, budget: float, risk_profile: str):
    llm = get_llm()
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
        llm=llm,
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
        llm=llm,
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
        llm=llm,
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
            "Return ONLY a JSON object with these exact keys, no markdown fences, no extra text:\n"
            "{\n"
            '  "symbol": string,\n'
            '  "verdict": "Buy" | "Hold" | "Avoid",\n'
            '  "conviction_score": integer 0-100,\n'
            '  "entry_range_pkr": string,\n'
            '  "stop_loss_pkr": string,\n'
            '  "position_size_pkr": string,\n'
            '  "fundamental_summary": string,\n'
            '  "technical_summary": string,\n'
            '  "key_risks": [string, ...],\n'
            '  "action_plan": [string, ...]\n'
            "}"
        ),
        expected_output="A single valid JSON object matching the schema above, and nothing else.",
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
    for sym in symbols:
        try:
            results.append(run_psx_analysis(sym, per_stock_budget, risk_profile))
        except Exception as e:
            results.append({"symbol": sym, "verdict": "Error", "conviction_score": None, "raw_output": str(e)})

    def _score(r):
        s = r.get("conviction_score")
        return s if isinstance(s, (int, float)) else -1

    return sorted(results, key=_score, reverse=True)
