import os
import base64
from google.cloud import firestore
from processor import GhostProcessor
from notifier import GhostNotifier

# Environment variables provided by GCC runtime memory
db = firestore.Client()
processor = GhostProcessor(os.getenv("GEMINI_API_KEY"))
notifier = GhostNotifier(
    os.getenv("TELEGRAM_BOT_TOKEN"), 
    os.getenv("TELEGRAM_CHAT_ID")
)

def ghost_watcher_entry(event, context):
    """
    Primary Entry Point: Triggered by Pub/Sub 'gmail-notifications' topic.
    """
    try:
        # Decode the Gmail push notification payload
        email_data = base64.b64decode(event['data']).decode('utf-8')
        
        # Analyze content via Gemini
        analysis = processor.parse_email(email_data)
        
        # Routing Logic
        if analysis.get('category') == 'priority':
            notifier.send_priority_alert(analysis)
        else:
            # Store in Firestore for the hourly summary task
            db.collection('summaries').add({
                'text': analysis['summary'],
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            
    except Exception as e:
        print(f"Watcher Error: {e}")

def hourly_summary_trigger(request):
    """
    Secondary Entry Point: Triggered by Cloud Scheduler HTTP request.
    """
    summaries_ref = db.collection('summaries')
    docs = summaries_ref.stream()
    
    summary_list = []
    for doc in docs:
        summary_list.append(doc.to_dict()['text'])
        # Clean up database after processing
        doc.reference.delete()
    
    if summary_list:
        notifier.send_hourly_batch(summary_list)
        return "Summary sent", 200
    
    return "No summaries found", 200