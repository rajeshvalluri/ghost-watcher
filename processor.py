import os
import base64
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import logging

# Set up logging for Cloud Functions
logger = logging.getLogger(__name__)

class GhostProcessor:
    def __init__(self, project_id):
        """
        Initializes Vertex AI and the Gmail API service.
        Validates environment variables from env.yaml immediately.
        """
        # 1. Capture Environment Variables
        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
        client_id = os.getenv("GMAIL_CLIENT_ID")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        
        # 2. Hard Validation of Config
        missing = [k for k, v in {
            "GMAIL_REFRESH_TOKEN": refresh_token,
            "GMAIL_CLIENT_ID": client_id,
            "GMAIL_CLIENT_SECRET": client_secret
        }.items() if not v]
        
        if missing:
            error_msg = f"MISSING CONFIG: {', '.join(missing)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Using us-central1 for stable Gemini 2.0 Flash access
            vertexai.init(project=project_id, location="us-central1")
            self.model = GenerativeModel("gemini-2.5-flash")
            
            # 3. Setup Gmail API Credentials
            self.creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token"
            )
            self.gmail_service = build('gmail', 'v1', credentials=self.creds)
            logger.info("GhostProcessor: Auth and AI successfully linked.")
        except Exception as e:
            logger.error(f"Initialization Error: {e}")
            raise

    def load_prompt(self):
        """
        Reads the user's custom instructions from prompt.txt.
        This allows for prompt tweaking without changing Python code.
        """
        try:
            # Cloud Functions bundle prompt.txt in the function's root directory
            prompt_path = os.path.join(os.path.dirname(__file__), 'prompt.txt')
            with open(prompt_path, 'r') as f:
                return f.read().strip()
        except Exception as e:
            logger.warning(f"Could not read prompt.txt: {e}. Using fallback.")
            return "Analyze this email. Categorize as PRIORITY or STANDARD and summarize."

    def get_full_email(self, message_id):
        """
        Fetches the actual email body and handles any file attachments.
        """
        try:
            msg = self.gmail_service.users().messages().get(
                userId='me', id=message_id, format='full'
            ).execute()
            
            # Extract Subject from headers
            headers = msg.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
            
            email_data = {
                "subject": subject,
                "body": msg.get('snippet', ''),
                "attachments": []
            }

            # Recursively check for attachments in message parts
            parts = msg.get('payload', {}).get('parts', [])
            if not parts and 'body' in msg.get('payload', {}):
                parts = [msg['payload']]

            for part in parts:
                if part.get('filename'):
                    att_id = part['body'].get('attachmentId')
                    att = self.gmail_service.users().messages().attachments().get(
                        userId='me', messageId=message_id, id=att_id).execute()
                    
                    email_data["attachments"].append({
                        "name": part['filename'],
                        "mimeType": part['mimeType'],
                        "data": att['data']
                    })
            return email_data
        except Exception as e:
            logger.error(f"Gmail Fetch Error: {e}")
            return None

    def analyze(self, email_data):
        """
        Processes text and image attachments using Gemini 2.0 Flash.
        """
        base_prompt = self.load_prompt()
        
        full_text_prompt = f"""
        {base_prompt}
        
        SUBJECT: {email_data['subject']}
        BODY: {email_data['body']}
        ATTACHMENTS: {[a['name'] for a in email_data['attachments']]}
        """
        
        content_parts = [full_text_prompt]
        
        # Add images to the multimodal prompt
        for att in email_data['attachments']:
            if "image" in att['mimeType']:
                try:
                    content_parts.append(Part.from_data(
                        data=base64.urlsafe_b64decode(att['data']),
                        mime_type=att['mimeType']
                    ))
                except Exception as e:
                    logger.error(f"Attachment Processing Error: {e}")

        try:
            response = self.model.generate_content(content_parts)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini Analysis Error: {e}")
            return "Classification failed due to AI error."

# Global singleton for the processor
processor = None

def get_processor():
    global processor
    if processor is None:
        # Defaults to your project ID if not explicitly in env
        p_id = os.getenv("PROJECT_ID", "agent-ghost-watcher")
        processor = GhostProcessor(p_id)
    return processor