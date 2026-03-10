import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials (get from https://my.telegram.org/apps)
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# Phone number (with country code, e.g., +1234567890)
PHONE_NUMBER = os.getenv('PHONE_NUMBER')

# Telethon session name (file prefix). Use different values for local vs host
# to avoid AuthKeyDuplicatedError from sharing the same session file.
SESSION_NAME = os.getenv('SESSION_NAME', 'session')

# Source groups - can be multiple (comma-separated in .env)
# Format: "group1,group2" or single "group1"
SOURCE_GROUPS_STR = os.getenv('SOURCE_GROUPS', '')
SOURCE_GROUPS = [g.strip() for g in SOURCE_GROUPS_STR.split(',') if g.strip()]

# Legacy support: if SOURCE_GROUP is set, use it
if not SOURCE_GROUPS and os.getenv('SOURCE_GROUP'):
    SOURCE_GROUPS = [os.getenv('SOURCE_GROUP')]

# Allowed sender IDs - comma-separated list (e.g., "123456789,987654321,2043323589")
ALLOWED_USER_IDS_STR = os.getenv('ALLOWED_USER_IDS', '')
ALLOWED_SENDER_IDS = []
if ALLOWED_USER_IDS_STR:
    for user_id in ALLOWED_USER_IDS_STR.split(','):
        user_id = user_id.strip()
        if user_id and user_id.isdigit():
            ALLOWED_SENDER_IDS.append(int(user_id))

# Legacy support: if individual USER_X_ID variables are set, use them too
for key in ['USER_A_ID', 'USER_B_ID', 'USER_C_ID', 'USER_PYTHON313_ID']:
    user_id = os.getenv(key, '0')
    if user_id and user_id != '0' and user_id.isdigit():
        user_id_int = int(user_id)
        if user_id_int not in ALLOWED_SENDER_IDS:
            ALLOWED_SENDER_IDS.append(user_id_int)

# Dual destinations based on market cap threshold
# MC < threshold → DESTINATION_UNDER_80K
# MC ≥ threshold → DESTINATION_80K_OR_MORE (also used as fallback when MC data unavailable)
DESTINATION_UNDER_80K = os.getenv('DESTINATION_UNDER_80K', 'me')
DESTINATION_80K_OR_MORE = os.getenv('DESTINATION_80K_OR_MORE', 'me')

# Market cap threshold (in USD) - default 80,000
MC_THRESHOLD = float(os.getenv('MC_THRESHOLD', '80000'))

# Max signals to retain; over capacity → delete oldest (FIFO)
MAX_SIGNALS = int(os.getenv('MAX_SIGNALS', '100'))

# Report destination (required for daily report + 1h/6h updates).
REPORT_DESTINATION = os.getenv('REPORT_DESTINATION', '').strip() or None

# Legacy support: if DESTINATION is set, use it as DESTINATION_80K_OR_MORE
if os.getenv('DESTINATION') and not os.getenv('DESTINATION_80K_OR_MORE'):
    DESTINATION_80K_OR_MORE = os.getenv('DESTINATION')

# Delay between forwards (seconds) - human-like behavior
FORWARD_DELAY = float(os.getenv('FORWARD_DELAY', '1.0'))

# Timezone for 🕐 in alerts and reports (e.g. America/New_York, Europe/Dubai, UTC)
DISPLAY_TIMEZONE = os.getenv('DISPLAY_TIMEZONE', 'America/New_York').strip()

# Redis (optional - enables caching, pub/sub events, rate limiting)
REDIS_URL = os.getenv('REDIS_URL', '').strip() or None

# Minimum market cap filter (USD) — signals below this MC at detection are skipped entirely
# Set to 0 to disable filtering (forward all signals regardless of MC)
MIN_MARKET_CAP = float(os.getenv('MIN_MARKET_CAP', '0'))

# Minimum liquidity filter (USD) — signals with liquidity below this are skipped
# Tokens with no/zero liquidity are almost always dead or honeypots
# Set to 0 to disable filtering
MIN_LIQUIDITY = float(os.getenv('MIN_LIQUIDITY', '5000'))

# Runner detection (near-real-time momentum alerts)
RUNNER_VELOCITY_MIN = float(os.getenv('RUNNER_VELOCITY_MIN', '1.5'))   # % per minute
RUNNER_VOL_ACCEL_MIN = float(os.getenv('RUNNER_VOL_ACCEL_MIN', '1.5'))  # 5m vol vs 24h rate
RUNNER_POLL_INTERVAL = int(os.getenv('RUNNER_POLL_INTERVAL', '90'))    # seconds

# Runner exit signal thresholds
RUNNER_EXIT_DRAWDOWN_PCT = float(os.getenv('RUNNER_EXIT_DRAWDOWN_PCT', '40'))    # % drawdown from peak
RUNNER_EXIT_LIQ_DRAIN_PCT = float(os.getenv('RUNNER_EXIT_LIQ_DRAIN_PCT', '50'))  # % liquidity removed
RUNNER_DEDUP_WINDOW = int(os.getenv('RUNNER_DEDUP_WINDOW', '1800'))              # seconds (30min)

# GOLD tier destination — high-conviction signals get their own channel
# If not set, GOLD signals go to the normal MC-based destination
DESTINATION_GOLD = os.getenv('DESTINATION_GOLD', '').strip() or None