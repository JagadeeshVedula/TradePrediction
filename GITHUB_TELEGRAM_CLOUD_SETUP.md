# ☁️ Triggering Stock AI in GitHub Actions from Telegram (No PC Required)

This guide shows you how to run your **Stock AI Predictor** entirely in the cloud, so that **when your system is shutdown**, you can still trigger predictions or have them run automatically.

---

## 🔍 Why the Bot Stopped Responding Earlier

1. **Local Bot Process**: `telegram_bot.py` / `run_telegram_bot.bat` was running as a local program on your computer. When your system was shutdown or asleep, the local process was closed, so no program was connected to Telegram to fetch your messages.
2. **Backlog Waiting**: The messages you sent (`Market News`, `Evening Report`, `Morning Prediction`) were held by Telegram's servers waiting for a listener.
3. **Private Chat Routing**: In `main.py`, reports were previously hardcoded to send only to the configured channel/group ID instead of replying back directly to your private chat.

---

## 🚀 How to Run When Your System is Shutdown

There are **3 simple ways** to run your pipeline without your local computer:

### Option 1: Automatic Scheduled Cloud Execution (Zero Effort, 100% Free)

The workflow [`.github/workflows/stock_scheduler.yml`](file:///c:/Users/Jagadeesh/Documents/TradePrediction/.github/workflows/stock_scheduler.yml) now has the automatic cron schedule enabled:

- **09:15 AM IST (Monday to Friday)**: GitHub automatically launches, fetches US & Asian market cues, analyzes Top 5 Indian stocks (< ₹500) using Gemini AI, and sends the morning prediction report directly to Telegram!
- **04:30 PM IST (Monday to Friday)**: GitHub automatically executes the evening P&L report and retrains the model.

**What you need to do**:
Ensure your GitHub repository has the necessary secrets configured:
1. Open your repository on GitHub (`https://github.com/JagadeeshVedula/TradePrediction`).
2. Go to **Settings** ➔ **Secrets and variables** ➔ **Actions**.
3. Under **Repository secrets**, ensure these are set:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token from @BotFather
   - `TELEGRAM_CHAT_ID`: `-5416154293,8006589467`
   - `GEMINI_API_KEY`: Your Google Gemini API Key

---

### Option 2: 1-Tap Trigger from Phone via GitHub Mobile App

You can trigger the pipeline anytime directly from your smartphone:
1. Install the free **GitHub** app on your iPhone or Android.
2. Open your repository: `JagadeeshVedula/TradePrediction`.
3. Tap **Actions** ➔ **Stock AI Predictor Automated Scheduler**.
4. Tap **Run workflow** ➔ Select `morning` (or `evening` or `full-cycle`) ➔ Tap **Run workflow**.
5. Within 1-2 minutes, GitHub Actions runs on GitHub's cloud servers and posts the report to your Telegram!

---

### Option 3: Telegram Bot ➔ GitHub Actions Webhook Relay (Free Cloudflare Worker)

If you want typing `/morning` or tapping buttons directly in Telegram to launch the GitHub Actions pipeline while your PC is off, use the free serverless script [`cloudflare_worker.js`](file:///c:/Users/Jagadeesh/Documents/TradePrediction/cloudflare_worker.js):

#### 2-Minute Setup:
1. **Create a GitHub Personal Access Token (PAT)**:
   - Go to GitHub ➔ **Settings** ➔ **Developer settings** ➔ **Personal access tokens** ➔ **Tokens (classic)**.
   - Click **Generate new token (classic)**.
   - Name: `telegram-worker-trigger`.
   - Check the **`repo`** (or **`workflow`**) box.
   - Click **Generate token** and copy it.

2. **Deploy Free Cloudflare Worker**:
   - Go to [dash.cloudflare.com](https://dash.cloudflare.com) (free account).
   - Go to **Workers & Pages** ➔ **Create application** ➔ **Create Worker**.
   - Name it `trade-telegram-bot` and click **Deploy**.
   - Click **Edit code**, paste the entire code from [`cloudflare_worker.js`](file:///c:/Users/Jagadeesh/Documents/TradePrediction/cloudflare_worker.js), and click **Deploy**.

3. **Add Environment Variables in Cloudflare**:
   - Go to Worker **Settings** ➔ **Variables and Secrets** ➔ **Add**:
     - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token from @BotFather
     - `GITHUB_TOKEN`: Your GitHub PAT token from Step 1.
     - `GITHUB_OWNER`: `JagadeeshVedula`
     - `GITHUB_REPO`: `TradePrediction`
     - `GITHUB_WORKFLOW`: `stock_scheduler.yml`

4. **Connect Telegram to Worker**:
   - Copy your worker URL (e.g., `https://trade-telegram-bot.yourname.workers.dev`).
   - Open your browser and visit:
     ```
     https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://trade-telegram-bot.yourname.workers.dev
     ```
   - You will see `{"ok":true,"result":true,"description":"Webhook was set"}`.

Now, whenever you prompt in Telegram from your phone, Cloudflare instantly catches the prompt, fires your GitHub Actions pipeline, and GitHub delivers the results back to Telegram!

---

## 🔄 Supported Telegram Commands & Actions

| Command / Button | Action in GitHub Cloud | Description |
| :--- | :--- | :--- |
| `🌅 Morning Prediction` or `/morning` | Mode: `morning` | Fetches US/Asian cues, scans Indian stocks (< ₹500), runs Gemini AI, sends top 5 picks. |
| `🔄 Full Pipeline` or `/full_pipeline` | Mode: `full-cycle` | **Full Day Session:** Runs morning prediction + 1m live intraday tracking until 03:30 PM + evening report & retraining! |
| `🌆 Evening Report` or `/evening` | Mode: `evening` | Post-close P&L calculation (+₹2 target / -₹1 stop loss) and continuous ML retraining. |
| `📊 Pipeline Status` or `/status` | Mode: API Query | Displays recent GitHub Actions workflow runs and their completion states. |

> [!TIP]
> If you have already deployed your Cloudflare Worker previously, make sure to copy the latest code from [`cloudflare_worker.js`](file:///c:/Users/Jagadeesh/Documents/TradePrediction/cloudflare_worker.js) into your Cloudflare Worker (`Quick Edit` / `Edit code`) and click **Deploy** so the `full pipeline` trigger is active on your worker!
