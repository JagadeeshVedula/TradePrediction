import os
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Supabase Cloud Settings
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "ml-models")

# Default Universe: Top Indian Stocks (NSE)
DEFAULT_INDIAN_TICKERS = [
    # IT & Technology Giants
    "INFY.NS",       # Infosys
    "TCS.NS",        # Tata Consultancy Services
    "WIPRO.NS",      # Wipro
    "HCLTECH.NS",    # HCL Technologies
    "TECHM.NS",      # Tech Mahindra
    "PERSISTENT.NS", # Persistent Systems
    "COFORGE.NS",    # Coforge
    "MPHASIS.NS",    # Mphasis
    "TATAELXSI.NS",  # Tata Elxsi
    "KPITTECH.NS",   # KPIT Technologies
    "OFSS.NS",       # Oracle Financial Services
    "ZENSARTECH.NS", # Zensar Technologies
    "SONATSOFTW.NS", # Sonata Software
    "CYIENT.NS",     # Cyient

    # Top Blue Chip & Growth Leaders
    "RELIANCE.NS",   # Reliance Industries
    "HDFCBANK.NS",   # HDFC Bank
    "ICICIBANK.NS",  # ICICI Bank
    "BHARTIARTL.NS", # Bharti Airtel
    "SBIN.NS",       # State Bank of India
    "LT.NS",         # Larsen & Toubro
    "ITC.NS",        # ITC Limited
    "HINDUNILVR.NS", # Hindustan Unilever
    "AXISBANK.NS",   # Axis Bank
    "KOTAKBANK.NS",  # Kotak Mahindra Bank
    "TATASTEEL.NS",  # Tata Steel
    "MARUTI.NS",     # Maruti Suzuki
    "SUNPHARMA.NS",  # Sun Pharma
    "NTPC.NS",       # NTPC
    "POWERGRID.NS",  # Power Grid Corp
    "TITAN.NS",      # Titan Company
    "BAJFINANCE.NS", # Bajaj Finance
    "ADANIENT.NS",   # Adani Enterprises
    "ADANIPORTS.NS", # Adani Ports
    "ULTRACEMCO.NS", # UltraTech Cement
    "JSWSTEEL.NS",   # JSW Steel
    "CIPLA.NS"       # Cipla
]

# Alias for backward compatibility across modules
DEFAULT_TECH_TICKERS = DEFAULT_INDIAN_TICKERS


# Database and Model Persistence Paths
DB_PATH = "market_data.db"
MODEL_PATH = "stock_model.pkl"
SCALER_PATH = "scaler.pkl"

# Prediction and Strategy Parameters
DEFAULT_GAIN_TARGET_PCT = 2.0  # Expected minimum target gain %
DEFAULT_STOP_LOSS_PCT = 1.5   # Risk stop loss %
LOOKBACK_DAYS = 60            # Days of historical market data for indicator computation
TOP_N_PREDICTIONS = 5         # Number of top tech stacks/stocks to recommend daily
