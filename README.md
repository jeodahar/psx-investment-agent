# PSX AI Investment Research Agent (v2)

A 3-agent CrewAI pipeline (Fundamental Analyst → Technical Analyst → Portfolio Manager) that researches
Pakistan Stock Exchange (PSX) stocks via DuckDuckGo search and Groq (`openai/gpt-oss-120b`), and returns
a structured, scored verdict — plus a mode to compare and rank several tickers at once.

## What changed from v1

- **Three agents instead of one advisor**: a fundamentals researcher, a technical analyst, and a
  portfolio manager that combines both (60% fundamentals / 40% technicals) into a 0–100 conviction score.
- **Structured JSON output** (verdict, conviction score, entry range, stop-loss, position size, risks,
  action plan) instead of free-form text — parsed with a safe fallback if the model doesn't return clean JSON.
- **Compare & rank mode**: enter 2–5 tickers and get them ranked by conviction score in one pass, with the
  budget automatically split across them.
- Research agent prompt now nudges toward PSX-specific sources (psx.com.pk, Business Recorder, Mettis Global)
  instead of generic global results.

## Project structure

```
psx-investment-agent/
├── .env.example
├── .gitignore
├── README.md
├── app.py
├── crew.py
└── requirements.txt
```

## 1. Push to GitHub

```bash
git init
git add .
git commit -m "PSX AI Agent v2 - 3-agent pipeline with scoring"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/psx-investment-agent.git
git push -u origin main
```

## 2. Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **New app** → pick this repo → branch `main` → main file `app.py`.
3. Under **Advanced settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "your_groq_api_key_here"
   ```
4. **Deploy.** The app reads the key from secrets automatically.

## 3. Run locally (optional)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # then fill in your GROQ_API_KEY
streamlit run app.py
```

## Important limits to know

- The agents read whatever DuckDuckGo surfaces — they do **not** pull live PSX tick data or guaranteed
  up-to-date financials. Treat the conviction score as a structured *opinion*, not a signal.
- "Compare & rank" runs the full pipeline once per ticker, so 5 tickers = 5x the API calls and time.
- No tool can legally or reliably predict daily price moves — use this to speed up research, not to
  replace it.

## Disclaimer

Educational tool only — not financial advice. Verify data against official PSX filings and consult an
SECP-registered advisor before trading.
