# 🚀 Top 5 Indian Stocks Gain Predictor & Continuous Retraining System

An automated Python Machine Learning pipeline designed to analyze Indian stock markets (NSE/BSE) daily, predict the **Top 5 Indian gainers for the day**, evaluate actual raise/fall movements post market close, continuously retrain the AI model with new feedback data, and send detailed reports directly to your **Telegram Channel**.

Hosted on **Supabase (PostgreSQL Database & Storage)** and scheduled via **GitHub Actions**, removing all local machine dependencies!

---

## 🌟 Key Features

1. **🌅 Morning Market Analysis with Google Gemini AI**:
   - Downloads real-time & intraday indicators for Indian stocks priced under ₹500 (`TATASTEEL.NS`, `WIPRO.NS`, `IOC.NS`, `EXIDEIND.NS`, `PNB.NS`, `SJVN.NS`, etc.).
   - Gathers **Global Market Cues**: Previous day US market close (S&P 500, Nasdaq, Dow Jones) and Singapore/Asian markets (Singapore Straits Times, Nikkei 225).
   - Scrapes live financial news from **Moneycontrol** & **Times of India** pre-market feeds.
   - Leverages **Google Gemini 2.5 Flash AI** to combine macroeconomic cues, domestic news catalysts, and technical indicators to pick the **Top 5 highest confidence stocks**.
   - Calculates target prices (+₹2.00 / pre-10am +₹10.00), stop losses (-₹1.00), and capital allocations (₹25,000 per stock).
   - **Trailing Stop Loss Strategy**: When a stock reaches its target amount (+₹2.00, e.g. Open @ 400 ➔ Target @ 402, Initial SL @ 399), the stop loss is pushed to +2 (moved to 401, locking in profit). After that, for every +1 increase in stock price (e.g. 403, 404), the stop loss moves up by 1 (402, 403), locking in higher profits on rallies.

2. **🌆 Evening Close Analysis**:
   - Downloads post-close actual market prices and 1-minute tick actions.
   - Computes share-by-share profit and loss breakdown against morning predictions.
   - Evaluates whether trailing stop loss (or pre-10am +₹10 / initial -₹1 stop loss) was triggered.

3. **🤖 Interactive Telegram Bot with Start/Stop Pipeline Controls**:
   - `/morning` — Trigger Morning Predictions immediately with Gemini AI & Global News analysis.
   - `/evening` — Trigger Evening Post-Market P&L Report & Retraining.
   - `/start_pipeline` — Start/Resume automated daily trading scheduler.
   - `/stop_pipeline` — Pause/Stop automated trading pipeline.
   - `/status` — View pipeline running state & Gemini AI connection status.
   - `/news` — Live US & Singapore market cues + Moneycontrol & TOI headlines.
   - `/set_key <API_KEY>` — Set or update your Google Gemini API key directly from Telegram!
   - `/help` — View commands guide with Telegram autocomplete support.

---

## ☁️ Supabase Setup (One-time Setup)

1. **Create Supabase Project**:
   - Create a free account at [Supabase](https://supabase.com).
   - Create a new project and go to **Project Settings -> API** to copy your **Project URL** and **API Key** (`service_role` recommended or `anon`).

2. **Run Database Migration (`schema.sql`)**:
   - Go to **SQL Editor** in your Supabase Dashboard.
   - Paste the contents of `schema.sql` (found in this repository) and click **Run**. This creates the `predictions`, `outcomes`, and `model_retraining_log` PostgreSQL tables.

3. **Create Storage Bucket (`ml-models`)**:
   - Go to **Storage -> Buckets** in Supabase.
   - Create a new bucket named `ml-models` (public or private).

4. **Add GitHub Repository Secrets**:
   - In your GitHub Repository, navigate to **Settings -> Secrets and variables -> Actions**.
   - Add the following Repository Secrets:
     - `SUPABASE_URL`: Your Supabase Project URL
     - `SUPABASE_KEY`: Your Supabase API Key
     - `SUPABASE_BUCKET`: `ml-models`
     - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API Token
     - `TELEGRAM_CHAT_ID`: Your Telegram Channel/Group Chat ID

---

## 🛠️ Local Development & Testing

### 1. Installation
Ensure Python 3.10+ is installed, then run:
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
Copy `.env.example` to `.env` and fill in your Supabase & Telegram credentials:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyZ
TELEGRAM_CHAT_ID=8006589467,-5544405822
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_supabase_key
SUPABASE_BUCKET=ml-models
```
*(Note: If Supabase credentials are omit from `.env`, the system automatically falls back to local SQLite `market_data.db` and local pickle files!)*

---

## 💻 Running the System

### Initial Baseline Model Training
```bash
python main.py --mode train-initial
```

### Morning Market Analysis (Top 5 Gainers Prediction)
```bash
python main.py --mode morning --send-telegram
```

### Evening Post-Market Close Report & Retraining Loop
```bash
python main.py --mode evening
```

### Full-Cycle Test Mode
```bash
python main.py --mode full-cycle
```

---

## 📁 Project Architecture

```
.
├── .github/workflows/
│   └── stock_scheduler.yml  # GitHub Actions automated morning & evening runner
├── config.py                 # System settings & Supabase cloud parameters
├── data_fetcher.py           # yfinance downloader & technical indicator calculations
├── ml_model.py               # ML ensemble predictor, retraining loop & Supabase Storage sync
├── database.py               # Supabase PostgreSQL database client (with SQLite fallback)
├── schema.sql                # Supabase DDL database migration script
├── reporter.py               # Markdown report generator
├── telegram_bot.py           # Telegram HTTP API integration
├── main.py                   # Main CLI controller
├── scheduler.py              # Local market hours runner (optional)
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables
└── README.md                 # System documentation
```
