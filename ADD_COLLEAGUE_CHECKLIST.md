# Adding a Colleague to the Digest — Quick Checklist

## Step-by-step guide

### ☐ 1. Get their Telegram Chat ID (5 minutes)

**Option A: Ask your colleague directly**
1. They message the bot with: `/start` or anything
2. They go to @userinfobot in Telegram
3. It tells them their "User ID"
4. **This is the chat_id** → e.g., `987654321`

**Option B: Check bot logs directly** (if you have API access)
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```
Replace `<YOUR_BOT_TOKEN>` with your actual Telegram bot token.
Look for the `"chat":{"id":...}` field — that's the chat_id.

### ☐ 2. Add to Railway environment variables (1 minute)

In Railway dashboard:
1. Go to your project
2. Click **Variables**
3. Add new variable:
   ```
   COLLEAGUE_TELEGRAM_CHAT_ID = 987654321
   ```
   (Replace `987654321` with their actual ID)

### ☐ 3. Update `digest_config.py` (30 seconds)

Find this section:
```python
TELEGRAM_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "You"),
    # (os.getenv("COLLEAGUE_TELEGRAM_CHAT_ID"), "Colleague Name"),
]
```

Uncomment and update the colleague line:
```python
TELEGRAM_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "You"),
    (os.getenv("COLLEAGUE_TELEGRAM_CHAT_ID"), "Sarah"),  # ← Uncomment & update name
]
```

### ☐ 4. Push to GitHub (1 minute)

```bash
git add digest_config.py
git commit -m "Add Sarah to digest recipients"
git push
```

Railway will auto-deploy. Done! ✓

---

## Verify it worked

Wait until the next scheduled time (8 AM, 12 PM, or 7 PM SGT).

Check Railway logs:
```
Recipients: ['You', 'Sarah']
→ Sending to You (123...)
✓ Message sent to 123...
→ Sending to Sarah (456...)
✓ Message sent to 456...
✓ Sent to 2/2 recipients
```

Both of you should receive the digest simultaneously.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Colleague not receiving messages | Verify their `TELEGRAM_CHAT_ID` with @userinfobot again; check Railway logs for errors |
| Only one recipient gets messages | Check that `TELEGRAM_RECIPIENTS` list has both entries with correct IDs |
| "403 Forbidden" error in logs | Verify `TELEGRAM_BOT_TOKEN` is correct in Railway variables |
| Deployment didn't trigger | Make sure you pushed to GitHub and Railway is set to auto-deploy |
| Messages are late or skipped | Check that Railway service is running (green status) and logs for any API errors |

---

## Removing a colleague later

Simply comment out or delete their line in `TELEGRAM_RECIPIENTS`:

```python
TELEGRAM_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "You"),
    # (os.getenv("COLLEAGUE_TELEGRAM_CHAT_ID"), "Sarah"),  # ← Commented out
]
```

Push to GitHub, Railway redeploys, and they stop receiving digests.

---

## Need different feeds or timing for the colleague?

If they want a **different digest** (e.g., only Infrastructure articles, or 2x daily instead of 3x), you'd deploy a **second instance** of `lng_digest.py` with separate config.

For now, **Option 3** gives you a shared digest to multiple recipients — the simplest setup.

---

**Total time to add one colleague: ~7 minutes**

Questions? Check the full guide: `MULTI_RECIPIENT_SETUP.md`
