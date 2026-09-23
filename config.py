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

# Default Universe: Top Indian Stocks (NSE) - Includes highly liquid stocks priced under Rs. 500
DEFAULT_INDIAN_TICKERS = [
    # Top Stocks & Liquid Candidates under Rs. 500
    "TATASTEEL.NS",   # Tata Steel
    "WIPRO.NS",      # Wipro
    "NTPC.NS",       # NTPC
    "POWERGRID.NS",  # Power Grid Corp
    "IOC.NS",        # Indian Oil Corporation
    "GAIL.NS",       # GAIL India
    "COALINDIA.NS",  # Coal India
    "BHEL.NS",       # Bharat Heavy Electricals
    "BEL.NS",        # Bharat Electronics
    "NATIONALUM.NS", # National Aluminium
    "PNB.NS",        # Punjab National Bank
    "UNIONBANK.NS",  # Union Bank of India
    "IRFC.NS",       # Indian Railway Finance Corp
    "SJVN.NS",       # SJVN Limited
    "SUZLON.NS",     # Suzlon Energy
    "IDFCFIRSTB.NS", # IDFC First Bank
    "EXIDEIND.NS",   # Exide Industries
    "NMDC.NS",       # NMDC Limited
    "CANBK.NS",      # Canara Bank
    "FEDERALBNK.NS", # Federal Bank
    "NHPC.NS",       # NHPC Limited
    "HUDCO.NS",      # HUDCO
    "MOTHERSON.NS",  # Samvardhana Motherson
    "SAIL.NS",       # Steel Authority of India
    "BANKBARODA.NS", # Bank of Baroda
    "TATAPOWER.NS",  # Tata Power
    "ASHOKLEY.NS",   # Ashok Leyland
    "MANAPPURAM.NS", # Manappuram Finance
    "TRIDENT.NS",    # Trident Limited
    "HFCL.NS",       # HFCL Limited
    "ZENSARTECH.NS", # Zensar Technologies
    "HINDCOPPER.NS", # Hindustan Copper
    "IDBI.NS",       # IDBI Bank


    # Additional Large Cap Universe for historical context
    "INFY.NS",
    "TCS.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "ITC.NS"
]

# Alias for backward compatibility across modules
DEFAULT_TECH_TICKERS = DEFAULT_INDIAN_TICKERS


# Database and Model Persistence Paths
DB_PATH = "market_data.db"
MODEL_PATH = "stock_model.pkl"
SCALER_PATH = "scaler.pkl"

# Prediction and Trade Parameters (User Strategy Rules)
MAX_STOCK_PRICE = 500.0         # Maximum stock price (Rs. 500)
INVESTMENT_PER_STOCK = 25000.0  # Assumed investment per stock (Rs. 25,000)
PROFIT_TARGET_INR = 1.0         # Profit target (+Rs. 1)
STOP_LOSS_INR = 3.0             # Stop loss (-Rs. 3)

DEFAULT_GAIN_TARGET_PCT = 2.0   # Minimum expected target gain % for model scoring
DEFAULT_STOP_LOSS_PCT = 1.5    # Fallback risk stop loss %
LOOKBACK_DAYS = 60             # Days of historical market data for indicator computation
TOP_N_PREDICTIONS = 5          # Number of top stocks to recommend daily

