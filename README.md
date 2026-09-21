# 🚀 Top 5 Indian Stocks Gain Predictor & Continuous Retraining System

An automated Python Machine Learning pipeline designed to analyze Indian stock markets (NSE/BSE) daily, predict the **Top 5 Indian gainers for the day**, evaluate actual raise/fall movements post market close, continuously retrain the AI model with new feedback data, and send detailed reports directly to your **Telegram Channel**.

Hosted on **Supabase (PostgreSQL Database & Storage)** and scheduled via **GitHub Actions**, removing all local machine dependencies!

---

## 🌟 Key Features

1. **🌅 Morning Market Analysis**:
   - Downloads real-time & intraday indicators for top Indian stock universe (`INFY.NS`, `TCS.NS`, `RELIANCE.NS`, `HDFCBANK.NS`, `WIPRO.NS`, `BHARTIARTL.NS`, `SBIN.NS`, `LT.NS`, etc.).
   - Predicts the **Top 5 expected Indian gainers** for the NSE/BSE market session.
   - Calculates target prices (in ₹), stop-loss thresholds, confidence scores, and key technical indicators driving the recommendation.

2. **🌆 Evening Close Analysis**:
   - Downloads post-close actual market prices (Open, Close, High, Low).
   - Computes actual raise/fall percentages and evaluates whether target prices were met.

3. **🧠 Continuous Retraining & Strategy Feedback Loop**:
   - Stores all predictions and actual outcome results into Supabase Cloud Database (`predictions`, `outcomes`, `model_retraining_log` tables).
   - Syncs trained ML ensemble models (`stock_model.pkl` + `scaler.pkl`) directly to Supabase Storage (`ml-models` bucket).
   - Dynamically adapts feature weights for next day's market predictions.

4. **☁️ Zero Local Machine Dependency (Hosted on Cloud)**:
   - Powered by **GitHub Actions** workflows running on cloud runners twice daily:
     - **Morning Analysis**: 09:15 AM IST (03:45 UTC) Mon-Fri
     - **Evening Close Report & Retraining**: 04:30 PM IST (11:00 UTC) Mon-Fri
   - Zero local server or PC needs to be left on.

5. **📲 Telegram Channel Integration**:
   - Formats clean, rich markdown reports with visual emojis (📈, 📉, 🎯, 🟢, 🔴).
   - Posts detailed morning & post-close performance reports directly to your Telegram Channel.

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
