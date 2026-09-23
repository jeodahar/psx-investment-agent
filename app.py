import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="PSX AI Investment Assistant", layout="wide", page_icon="📈")

PKT = ZoneInfo("Asia/Karachi")


def now_str() -> str:
    return datetime.now(PKT).strftime("%d %b %Y, %I:%M:%S %p PKT")


# --- Modern styling --------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: radial-gradient(circle at 10% 0%, #101b2d 0%, #0a1220 45%, #060a12 100%);
    color: #e8ecf3;
}
section[data-testid="stSidebar"] {
    background: #0b1420;
    border-right: 1px solid rgba(255,255,255,0.06);
}
.hero {
    padding: 1.6rem 1.8rem;
    border-radius: 20px;
    background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(59,130,246,0.10));
    border: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 1.2rem;
}
.hero h1 { margin: 0; font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; }
.hero p { margin: 0.35rem 0 0 0; color: #9fb0c3; font-size: 0.95rem; }

.stock-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    height: 100%;
}
.stock-card .ticker { font-weight: 700; font-size: 1.05rem; color: #f5f7fa; }
.stock-card .sector { color: #8ea3b8; font-size: 0.82rem; margin-top: 2px; }
.stock-card .tag {
    display: inline-block; margin-top: 8px; padding: 2px 10px;
    border-radius: 999px; font-size: 0.72rem; font-weight: 600;
    background: rgba(16,185,129,0.15); color: #34d399;
}

.verdict-card {
    border-radius: 18px;
    padding: 1.2rem 1.4rem;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.03);
    margin-bottom: 0.9rem;
}
.verdict-buy { border-left: 5px solid #22c55e; }
.verdict-hold { border-left: 5px solid #eab308; }
.verdict-avoid { border-left: 5px solid #ef4444; }
.verdict-unknown { border-left: 5px solid #64748b; }

.badge { display: inline-block; padding: 3px 12px; border-radius: 999px; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.02em; }
.badge-buy { background: rgba(34,197,94,0.18); color: #4ade80; }
.badge-hold { background: rgba(234,179,8,0.18); color: #facc15; }
.badge-avoid { background: rgba(239,68,68,0.18); color: #f87171; }
.badge-unknown { background: rgba(100,116,139,0.18); color: #94a3b8; }

.timestamp { color: #6b7d90; font-size: 0.78rem; margin-top: 0.5rem; }
.psx-lock-note { color: #7ea9ff; font-size: 0.8rem; margin-top: 0.4rem; }

div.stButton > button { border-radius: 10px; font-weight: 600; }
hr { border-color: rgba(255,255,255,0.08); }
</style>
""", unsafe_allow_html=True)

# --- Hero header ------------------------------------------------------------
st.markdown("""
<div class="hero">
  <h1>🇵🇰 PSX AI Investment Research Agent</h1>
  <p>CrewAI 3-agent pipeline · Groq (openai/gpt-oss-120b) · DuckDuckGo Search · Live PSX-only market data</p>
</div>
""", unsafe_allow_html=True)

# --- API key resolution: Streamlit Cloud secrets -> sidebar input -> .env --
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

st.sidebar.header("🔑 API Settings")
if not os.getenv("GROQ_API_KEY"):
    api_key_input = st.sidebar.text_input(
        "Groq API Key", type="password",
        help="Not needed if GROQ_API_KEY is set in Streamlit Cloud secrets"
    )
    if api_key_input:
        os.environ["GROQ_API_KEY"] = api_key_input
else:
    st.sidebar.success("Groq API Key loaded from secrets ✅")

st.sidebar.markdown("---")
st.sidebar.caption(f"🕒 Session time: {now_str()}")

# --- Featured stocks ---------------------------------------------------------
st.subheader("📌 Featured Blue-Chip Stocks on PSX")
featured = [
    ("FFC", "Fertilizer", "High Dividend"),
    ("SYS", "Technology", "Dollar Revenue"),
    ("OGDC", "Energy", "Value Play"),
    ("MEBL", "Banking", "Shariah Leader"),
]
cols = st.columns(4)
for col, (ticker, sector, tag) in zip(cols, featured):
    with col:
        st.markdown(f"""
        <div class="stock-card">
          <div class="ticker">{ticker}</div>
          <div class="sector">{sector}</div>
          <div class="tag">{tag}</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# --- Curated PSX symbol list (keeps the chart locked to PSX, never global) -
PSX_SYMBOLS = {
    "KSE-100 Index": "KSE100",
    "Fauji Fertilizer — FFC": "FFC",
    "Oil & Gas Development — OGDC": "OGDC",
    "Systems Limited — SYS": "SYS",
    "Meezan Bank — MEBL": "MEBL",
    "Habib Bank — HBL": "HBL",
    "Lucky Cement — LUCK": "LUCK",
    "Pakistan Petroleum — PPL": "PPL",
    "Engro Fertilizers — EFERT": "EFERT",
    "United Bank — UBL": "UBL",
}


def render_verdict(v: dict, generated_at: str = None):
    if v.get("verdict") in (None, "Unparsed", "Error"):
        st.warning(f"Could not fully parse a structured result for {v.get('symbol')}.")
        with st.expander("Raw agent output"):
            st.write(v.get("raw_output", "No output captured."))
        if generated_at:
            st.markdown(f'<div class="timestamp">🕒 Generated: {generated_at}</div>', unsafe_allow_html=True)
        return

    verdict = v.get("verdict", "")
    css_class = {"Buy": "verdict-buy", "Hold": "verdict-hold", "Avoid": "verdict-avoid"}.get(verdict, "verdict-unknown")
    badge_class = {"Buy": "badge-buy", "Hold": "badge-hold", "Avoid": "badge-avoid"}.get(verdict, "badge-unknown")

    st.markdown(f"""
    <div class="verdict-card {css_class}">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
        <div style="font-size:1.2rem; font-weight:800;">{v.get('symbol')}</div>
        <span class="badge {badge_class}">{verdict} · {v.get('conviction_score')}/100</span>
      </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Entry Range (PKR)", v.get("entry_range_pkr", "—"))
    c2.metric("Stop-Loss (PKR)", v.get("stop_loss_pkr", "—"))
    c3.metric("Suggested Position (PKR)", v.get("position_size_pkr", "—"))

    st.markdown(f"**Fundamentals:** {v.get('fundamental_summary', '—')}")
    st.markdown(f"**Technicals:** {v.get('technical_summary', '—')}")

    risks = v.get("key_risks") or []
    if risks:
        st.markdown("**Key risks:**")
        for r in risks:
            st.markdown(f"- {r}")

    plan = v.get("action_plan") or []
    if plan:
        st.markdown("**Action plan:**")
        for i, step in enumerate(plan, 1):
            st.markdown(f"{i}. {step}")

    if generated_at:
        st.markdown(f'<div class="timestamp">🕒 Generated: {generated_at}</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


tab_single, tab_compare, tab_chart, tab_chat = st.tabs(
    ["🔍 Analyze one stock", "⚖️ Compare & rank several", "📉 Live PSX Chart", "💬 Chat Advisor"]
)

with tab_single:
    with st.form("psx_single_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            stock_symbol = st.text_input("PSX Stock Symbol", value="FFC").upper()
        with c2:
            budget = st.number_input("Investment Budget (PKR)", min_value=10000, value=100000, step=10000)
        with c3:
            risk_profile = st.selectbox(
                "Risk Profile",
                ["Low (Conservative)", "Moderate (Balanced)", "High (Growth)"],
                key="single_risk"
            )
        submit = st.form_submit_button("🚀 Analyze")

    if submit:
        if not os.getenv("GROQ_API_KEY"):
            st.error("Please provide a Groq API Key in the sidebar, or set it in Streamlit Cloud secrets.")
        else:
            with st.spinner(f"Researching {stock_symbol}..."):
                try:
                    from crew import run_psx_analysis
                    result = run_psx_analysis(stock_symbol, budget, risk_profile)
                    gen_time = now_str()
                    st.success("Analysis complete.")
                    render_verdict(result, generated_at=gen_time)
                except Exception as e:
                    st.error(f"Error executing agent: {str(e)}")

with tab_compare:
    st.caption("Enter 2–5 tickers to research in one pass; results are ranked by conviction score.")
    with st.form("psx_compare_form"):
        symbols_raw = st.text_input("PSX Symbols (comma-separated)", value="FFC, OGDC, SYS, MEBL")
        c1, c2 = st.columns(2)
        with c1:
            total_budget = st.number_input("Total Budget to Split (PKR)", min_value=10000, value=200000, step=10000)
        with c2:
            risk_profile_cmp = st.selectbox(
                "Risk Profile",
                ["Low (Conservative)", "Moderate (Balanced)", "High (Growth)"],
                key="compare_risk"
            )
        submit_cmp = st.form_submit_button("🚀 Compare & Rank")

    if submit_cmp:
        symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()][:5]
        if not os.getenv("GROQ_API_KEY"):
            st.error("Please provide a Groq API Key in the sidebar, or set it in Streamlit Cloud secrets.")
        elif len(symbols) < 2:
            st.warning("Enter at least 2 symbols to compare.")
        else:
            with st.spinner(f"Researching {', '.join(symbols)}... this runs each stock through the full pipeline with paced requests, so it can take several minutes."):
                try:
                    from crew import compare_stocks
                    ranked = compare_stocks(symbols, total_budget, risk_profile_cmp)
                    batch_time = now_str()
                    st.success("Comparison complete — ranked highest conviction first.")
                    st.caption(f"🕒 Batch completed: {batch_time} (stocks were researched one at a time, so individual results finished a bit earlier than this)")
                    for v in ranked:
                        render_verdict(v)
                        st.divider()
                except Exception as e:
                    st.error(f"Error executing agent: {str(e)}")

with tab_chart:
    st.caption("Live chart data — locked to Pakistan Stock Exchange (PSX) listings only, never a global/other-exchange ticker.")

    tape_symbols = [{"proName": f"PSX:{sym}", "title": label.split("—")[-1].strip()} for label, sym in PSX_SYMBOLS.items()]
    tape_config = json.dumps(tape_symbols)
    ticker_tape_html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
      {{
        "symbols": {tape_config},
        "showSymbolLogo": true,
        "isTransparent": true,
        "displayMode": "adaptive",
        "colorTheme": "dark",
        "locale": "en"
      }}
      </script>
    </div>
    """
    components.html(ticker_tape_html, height=60)

    col_a, col_b = st.columns([3, 1])
    with col_a:
        label_choice = st.selectbox("Choose a PSX symbol", list(PSX_SYMBOLS.keys()), index=0)
    with col_b:
        custom_toggle = st.checkbox("Custom PSX symbol", value=False)

    if custom_toggle:
        custom_symbol = st.text_input("PSX ticker (no prefix, e.g. HUBCO)", value="FFC").strip().upper()
        chart_symbol = custom_symbol if custom_symbol else "KSE100"
    else:
        chart_symbol = PSX_SYMBOLS[label_choice]

    tv_symbol = f"PSX:{chart_symbol}"

    tradingview_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%",
        "height": 480,
        "symbol": "{tv_symbol}",
        "interval": "D",
        "timezone": "Asia/Karachi",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#0b1420",
        "enable_publishing": false,
        "allow_symbol_change": false,
        "hide_side_toolbar": false,
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    components.html(tradingview_html, height=500, scrolling=False)

    st.markdown(f'<div class="timestamp">🕒 Chart loaded: {now_str()}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="psx-lock-note">🔒 Locked to PSX — the widget\'s own symbol-change search is disabled '
        'so it can\'t drift to a non-PSX / global ticker. Use the dropdown above to switch symbols instead.</div>',
        unsafe_allow_html=True
    )
    if st.button("🔄 Refresh timestamp"):
        st.rerun()

with tab_chat:
    st.caption(
        "Ask general PSX investing questions — sector picks, how to size a position, what a P/E ratio "
        "means, etc. This is a single lightweight assistant call, separate from the research pipeline "
        "in the other tabs, so it stays fast."
    )

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    use_search = st.checkbox(
        "🔎 Include a live web search for this question (slower, more current)",
        value=False,
        key="chat_use_search"
    )

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("time"):
                st.markdown(f'<div class="timestamp">🕒 {msg["time"]}</div>', unsafe_allow_html=True)

    user_prompt = st.chat_input("Ask about PSX investing...")
    if user_prompt:
        if not os.getenv("GROQ_API_KEY"):
            st.error("Please provide a Groq API Key in the sidebar, or set it in Streamlit Cloud secrets.")
        else:
            user_time = now_str()
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt, "time": user_time})
            with st.chat_message("user"):
                st.markdown(user_prompt)
                st.markdown(f'<div class="timestamp">🕒 {user_time}</div>', unsafe_allow_html=True)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        from crew import chat_with_advisor
                        api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_messages]
                        reply = chat_with_advisor(api_messages, use_search=use_search)
                    except Exception as e:
                        reply = f"Error: {str(e)}"
                reply_time = now_str()
                st.markdown(reply)
                st.markdown(f'<div class="timestamp">🕒 {reply_time}</div>', unsafe_allow_html=True)

            st.session_state.chat_messages.append({"role": "assistant", "content": reply, "time": reply_time})

    if st.session_state.chat_messages:
        if st.button("🗑️ Clear chat"):
            st.session_state.chat_messages = []
            st.rerun()

st.info(
    "⚠️ **Disclaimer:** Educational tool only, not financial advice. The conviction score reflects the "
    "AI's read of publicly available search results, which may be incomplete or outdated. Verify data "
    "against official PSX filings and consult an SECP-registered advisor before trading."
)
