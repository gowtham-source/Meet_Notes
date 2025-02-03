import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google Calendar API Configuration
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

# Recording Configuration
RECORDING_DIR = 'recordings'
TRANSCRIPTION_DIR = 'transcriptions'

# Create necessary directories if they don't exist
os.makedirs(RECORDING_DIR, exist_ok=True)
os.makedirs(TRANSCRIPTION_DIR, exist_ok=True)

# Browser configuration
CHROME_PROFILE_PATH = os.path.join(os.getcwd(), 'chrome_profile')
os.makedirs(CHROME_PROFILE_PATH, exist_ok=True) 