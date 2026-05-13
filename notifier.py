import requests

class GhostNotifier:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_priority_alert(self, data):
        """Sends an immediate rich notification for priority emails."""
        text = (
            f"🔔 *Priority: {data.get('sender_type', 'Notification')}*\n"
            f"📝 {data['summary']}\n"
            f"💰 Amount: {data.get('amount', 'N/A')}\n"
            f"📅 Date: {data.get('due_date', 'N/A')}"
        )
        self._dispatch(text)

    def send_hourly_batch(self, summaries):
        """Sends the hourly digest of standard emails."""
        text = "📋 *Hourly Email Summary*\n\n" + "\n".join([f"• {s}" for s in summaries])
        self._dispatch(text)

    def _dispatch(self, text):
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        requests.post(self.base_url, json=payload)