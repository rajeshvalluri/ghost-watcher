import base64
import json
import os
import requests
import functions_framework
from processor import get_processor

@functions_framework.cloud_event
def ghost_watcher_entry(cloud_event):
    try:
        # 1. Parse Pub/Sub Notification
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
        payload = json.loads(data)
        
        # 2. Get the latest message ID
        proc = get_processor()
        list_res = proc.gmail_service.users().messages().list(userId='me', maxResults=1).execute()
        msg_id = list_res.get('messages', [{}])[0].get('id')

        if not msg_id:
            return "No messages found", 200

        # 3. Fetch full content and attachments
        email_payload = proc.get_full_email(msg_id)
        
        # 4. Process with Gemini
        report = proc.analyze(email_payload)

        # 5. Telegram Notification
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        msg_text = f"<b>👻 Ghost Watcher</b>\n\n{report}"
        
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg_text, "parse_mode": "HTML"})

        return "OK", 200
    except Exception as e:
        print(f"Global Failure: {e}")
        return "Error", 200