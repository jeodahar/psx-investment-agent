import os
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="PSX AI Investment Assistant", layout="wide", page_icon="📈")

st.title("🇵🇰 PSX AI Investment Research Agent")
st.caption("Powered by CrewAI (3-agent pipeline) + Groq (openai/gpt-oss-120b) + DuckDuckGo Search")

# --- API key resolution: Streamlit Cloud secrets -> sidebar input -> .env ---
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

st.subheader("📌 Featured Blue-Chip Stocks on PSX")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="FFC (Fauji Fertilizer)", value="Fertilizer", delta="High Dividend")
with col2:
    st.metric(label="SYS (Systems Ltd)", value="Technology", delta="Dollar Revenue")
with col3:
    st.metric(label="OGDC (Oil & Gas)", value="Energy", delta="Value Play")
with col4:
    st.metric(label="MEBL (Meezan Bank)", value="Banking", delta="Shariah Leader")

st.divider()


def render_verdict(v: dict):
    if v.get("verdict") in (None, "Unparsed", "Error"):
        st.warning(f"Could not fully parse a structured result for {v.get('symbol')}.")
        with st.expander("Raw agent output"):
            st.write(v.get("raw_output", "No output captured."))
        return

    badge = {"Buy": "🟢", "Hold": "🟡", "Avoid": "🔴"}.get(v.get("verdict"), "⚪")
    st.markdown(f"### {badge} {v.get('symbol')} — {v.get('verdict')}  (Conviction: {v.get('conviction_score')}/100)")

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


tab_single, tab_compare, tab_chart, tab_chat = st.tabs(
    ["🔍 Analyze one stock", "⚖️ Compare & rank several", "📉 Live Market Chart", "💬 Chat Advisor"]
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
                    st.success("Analysis complete.")
                    render_verdict(result)
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
            with st.spinner(f"Researching {', '.join(symbols)}... this runs each stock through the full pipeline, so it can take a few minutes."):
                try:
                    from crew import compare_stocks
                    ranked = compare_stocks(symbols, total_budget, risk_profile_cmp)
                    st.success("Comparison complete — ranked highest conviction first.")
                    for v in ranked:
                        render_verdict(v)
                        st.divider()
                except Exception as e:
                    st.error(f"Error executing agent: {str(e)}")

with tab_chart:
    st.caption(
        "Live TradingView chart for PSX. Type any PSX symbol (e.g. KSE100, FFC, OGDC, SYS, MEBL, HBL) "
        "or use the chart's own symbol search."
    )
    chart_symbol = st.text_input("Symbol", value="KSE100", key="chart_symbol").strip().upper()
    tv_symbol = f"PSX:{chart_symbol}" if chart_symbol else "PSX:KSE100"

    tradingview_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%",
        "height": 520,
        "symbol": "{tv_symbol}",
        "interval": "D",
        "timezone": "Asia/Karachi",
        "theme": "light",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "hide_side_toolbar": false,
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    components.html(tradingview_html, height=540, scrolling=False)
    st.caption(
        "Chart data comes directly from TradingView, not from this app's own agents — "
        "if a symbol shows no data, try the chart's built-in symbol search icon to find the exact PSX listing."
    )

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

    user_prompt = st.chat_input("Ask about PSX investing...")
    if user_prompt:
        if not os.getenv("GROQ_API_KEY"):
            st.error("Please provide a Groq API Key in the sidebar, or set it in Streamlit Cloud secrets.")
        else:
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        from crew import chat_with_advisor
                        reply = chat_with_advisor(st.session_state.chat_messages, use_search=use_search)
                    except Exception as e:
                        reply = f"Error: {str(e)}"
                st.markdown(reply)

            st.session_state.chat_messages.append({"role": "assistant", "content": reply})

    if st.session_state.chat_messages:
        if st.button("🗑️ Clear chat"):
            st.session_state.chat_messages = []
            st.rerun()

st.info(
    "⚠️ **Disclaimer:** Educational tool only, not financial advice. The conviction score reflects the "
    "AI's read of publicly available search results, which may be incomplete or outdated. Verify data "
    "against official PSX filings and consult an SECP-registered advisor before trading."
)
