
python

from lng_digest import send_to_telegram
from digest_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Test sending a simple message
result = send_to_telegram(
    f"Test message to chat {TELEGRAM_CHAT_ID}",
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID
)
print(result)