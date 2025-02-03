from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os.path
import datetime
import logging
import pytz
from config import SCOPES, CREDENTIALS_FILE, TOKEN_FILE

logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self):
        self.creds = None
        self.service = None
        self.timezone = pytz.timezone('Asia/Kolkata')  # Indian timezone
        self.authenticate()

    def authenticate(self):
        """Authenticate with Google Calendar API using OAuth 2.0"""
        try:
            if os.path.exists(TOKEN_FILE):
                self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
                logger.info("Loaded existing credentials from token file")

            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info("Refreshing expired credentials")
                    self.creds.refresh(Request())
                else:
                    logger.info("Starting new OAuth2 flow")
                    if not os.path.exists(CREDENTIALS_FILE):
                        logger.error(f"Credentials file not found: {CREDENTIALS_FILE}")
                        raise FileNotFoundError(f"Missing {CREDENTIALS_FILE}")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(TOKEN_FILE, 'w') as token:
                    token.write(self.creds.to_json())
                logger.info("Saved new credentials to token file")

            self.service = build('calendar', 'v3', credentials=self.creds)
            logger.info("Successfully initialized Calendar service")
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise

    def get_upcoming_meetings(self, time_window_minutes=60):
        """Get upcoming Google Meet meetings within the specified time window"""
        try:
            # Get current time in UTC
            now = datetime.datetime.now(pytz.UTC)
            time_window = now + datetime.timedelta(minutes=time_window_minutes)

            logger.info(f"Fetching meetings between {now} and {time_window}")
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat(),
                timeMax=time_window.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            meetings = []
            for event in events_result.get('items', []):
                # Check if event has Google Meet link
                if 'hangoutLink' in event:
                    # Ensure timezone information is preserved
                    start = event['start'].get('dateTime')
                    end = event['end'].get('dateTime')
                    
                    if start and end:  # Only process events with specific times (not all-day events)
                        meeting_info = {
                            'id': event['id'],
                            'summary': event['summary'],
                            'start': start,
                            'end': end,
                            'meet_link': event['hangoutLink']
                        }
                        meetings.append(meeting_info)
                        
                        # Convert to local time for logging
                        start_local = datetime.datetime.fromisoformat(start).astimezone(self.timezone)
                        logger.info(f"Found meeting: {meeting_info['summary']} at {start_local}")

            return meetings
            
        except Exception as e:
            logger.error(f"Error fetching meetings: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return [] 