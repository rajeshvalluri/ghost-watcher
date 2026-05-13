import os
import base64
from google.cloud import firestore
from dotenv import load_dotenv
from processor import GhostProcessor
from notifier import GhostNotifier

# Initialize environment and clients
load_dotenv()
db = firestore.Client()
processor = GhostProcessor(os.getenv("GEMINI_API_KEY"))
notifier = GhostNotifier(
    os.getenv("TELEGRAM_BOT_TOKEN"), 
    os.getenv("TELEGRAM_CHAT_ID")
)

def ghost_watcher_entry(event, context):
    """
    Trigger 1: New Email via Pub/Sub.
    """
    try:
        # Decode the Gmail Pub/Sub payload
        email_data = base64.b64decode(event['data']).decode('utf-8')
        
        # Analyze with Gemini
        analysis = processor.parse_email(email_data)
        
        # Priority Logic
        if analysis.get('category') == 'priority':
            notifier.send_priority_alert(analysis)
        else:
            # Store in Firestore for the hourly batch
            db.collection('summaries').add({
                'text': analysis['summary'],
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            
    except Exception as e:
        print(f"Orchestrator Error: {e}")

def hourly_summary_trigger(event, context):
    """
    Trigger 2: Cloud Scheduler (Hourly).
    """
    summaries_ref = db.collection('summaries')
    docs = summaries_ref.stream()
    
    summary_list = []
    for doc in docs:
        summary_list.append(doc.to_dict()['text'])
        doc.reference.delete() # Clear processed items
    
    if summary_list:
        notifier.send_hourly_batch(summary_list)