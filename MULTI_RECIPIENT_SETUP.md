# Multi-Recipient Setup Guide (Option 3)

This guide walks through adding your colleague to the LNG digest using **Option 3** — one digest instance sending to multiple recipients.

## What Changed

**Before:** `digest_config.py` had a single `TELEGRAM_CHAT_ID`  
**Now:** `digest_config.py` has `TELEGRAM_RECIPIENTS` — a list of recipients

**Example:**
```python
TELEGRAM_RECIPIENTS = [
    ("123456789", "You"),
    ("987654321", "Colleague Name"),
]
```

`lng_digest.py` now loops through all recipients and sends the same digest to each at the scheduled times (8 AM, 12 PM, 7 PM SGT).

---

## Step 1: Get Your Colleague's Telegram Chat ID

Your colleague needs to:

1. **Start a conversation** with your Telegram bot (the one sending the digest)
2. **Send any message** to the bot (e.g., "hi" or "/start")
3. Use [@userinfobot](https://t.me/userinfobot) to find their **User ID**
   - Chat with @userinfobot
   - It will reply with your ID
   - This is your `chat_id`

**Or** check your bot's message logs:
- Go to `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
- Replace `<YOUR_BOT_TOKEN>` with your actual token
- Look for your colleague's incoming message — it will have a `chat.id` field

---

## Step 2: Update Environment Variables (Railway.app)

Add your colleague's chat ID as a new environment variable in Railway:

1. Go to your Railway project dashboard
2. Click **Variables**
3. Add a new variable:
   ```
   COLLEAGUE_TELEGRAM_CHAT_ID = "987654321"
   ```
   (Replace `987654321` with the actual chat ID)

**Note:** If your colleague needs a different bot token (unlikely), also add:
```
COLLEAGUE_TELEGRAM_BOT_TOKEN = "token_here"
```

---

## Step 3: Update `digest_config.py`

Uncomment and modify the colleague entry:

```python
TELEGRAM_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "You"),
    (os.getenv("COLLEAGUE_TELEGRAM_CHAT_ID"), "Colleague Name"),  # ← Uncomment & update name
]
```

Or for multiple colleagues:

```python
TELEGRAM_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "Aaron"),
    (os.getenv("COLLEAGUE_TELEGRAM_CHAT_ID"), "Sarah"),
    (os.getenv("COLLEAGUE_2_TELEGRAM_CHAT_ID"), "James"),
]
```

---

## Step 4: Deploy

1. **Commit** the updated `digest_config.py` to GitHub:
   ```bash
   git add digest_config.py
   git commit -m "Add colleague to digest recipients"
   git push
   ```

2. **Railway will auto-redeploy** (if you have auto-deploy enabled)

3. **Verify** in the Railway logs:
   ```
   Recipients: ['You', 'Colleague Name']
   ```

---

## Testing

Before the next scheduled time (8 AM, 12 PM, or 7 PM SGT), you can test manually:

```python
# In a Python shell with the same environment
from lng_digest import LNGDigest

digest = LNGDigest()
digest.run_digest("Test 12:00 PM")
```

Both you and your colleague should receive the digest simultaneously.

---

## How It Works (Behind the Scenes)

The updated `lng_digest.py` has a new method:

```python
def send_to_all_recipients(self, text, recipients):
    """Send message to all configured recipients."""
    for chat_id, recipient_name in recipients:
        self.send_message(text, chat_id)
```

At each scheduled time (8 AM, 12 PM, 7 PM):
1. **One** digest is generated from RSS feeds
2. **One** summary is created by Claude AI
3. **One** formatted message is created
4. That **same message** is sent to **all recipients** (with 0.5s delay between sends)

---

## Removing a Recipient

Simply comment out or delete the line in `TELEGRAM_RECIPIENTS`:

```python
TELEGRAM_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "You"),
    # (os.getenv("COLLEAGUE_TELEGRAM_CHAT_ID"), "Colleague Name"),  # ← Commented out
]
```

Then redeploy.

---

## Troubleshooting

### Colleague not receiving messages
- [ ] Verify their `TELEGRAM_CHAT_ID` is correct (use @userinfobot again)
- [ ] Check Railway logs for errors: `✗ Failed to send to <chat_id>`
- [ ] Ensure the bot hasn't blocked them (ask colleague to /start the bot again)

### Only one recipient getting messages
- [ ] Check that `TELEGRAM_RECIPIENTS` has both entries with correct chat IDs
- [ ] Verify environment variables are set in Railway
- [ ] Restart the service (Railway will auto-restart on next deployment)

### "403 Forbidden" error in logs
- The bot token is invalid or the bot was removed from Telegram
- Check your `TELEGRAM_BOT_TOKEN` in Railway variables

---

## Future Enhancements

If you later want **different feeds or schedules per recipient**, you'd need separate digest instances. But for now, **Option 3** (one digest, many recipients) is the cleanest setup.

---

**Questions?** Check the logs on Railway or test locally first.
