import google.generativeai as genai
import json
import os

class GhostProcessor:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        # Using flash for efficiency and speed
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def parse_email(self, email_body):
        """
        Uses Gemini to classify the email and extract key financial/date data.
        """
        prompt = (
            "Analyze this email. Return ONLY a JSON object with these keys: "
            "'category' (priority or standard), 'summary' (1 sentence), "
            "'amount' (if found), 'due_date' (if found), 'sender_type'. "
            "Priority categories: School, Bank, Utility, Casting Agent, or Invoice."
        )
        
        try:
            response = self.model.generate_content(f"{prompt}\n\nEmail: {email_body}")
            # Ensure we only get the JSON part of the string
            content = response.text.strip().replace('```json', '').replace('
```', '')
            return json.loads(content)
        except Exception as e:
            print(f"AI Parsing Error: {e}")
            return {"category": "standard", "summary": "Error parsing email."}