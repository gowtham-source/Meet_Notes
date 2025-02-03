import time
import threading
import logging
from datetime import datetime, timedelta
import pytz
from calendar_service import CalendarService
from meeting_recorder import MeetingRecorder

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('meet_notes.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MeetingManager:
    def __init__(self):
        logger.info("Initializing MeetingManager...")
        self.calendar_service = CalendarService()
        self.meeting_recorder = MeetingRecorder()
        self.current_meeting = None
        self.timezone = pytz.timezone('Asia/Kolkata')  # Indian timezone
        self.failed_meetings = set()  # Track failed meeting attempts

    def is_valid_meeting(self, meeting):
        """Check if a meeting is valid and hasn't failed before"""
        try:
            # Skip if we've already failed to join this meeting
            if meeting['id'] in self.failed_meetings:
                logger.info(f"Skipping previously failed meeting: {meeting['summary']}")
                return False

            # Verify the meeting link format
            if not meeting.get('meet_link') or 'meet.google.com' not in meeting['meet_link']:
                logger.error(f"Invalid meeting link format: {meeting.get('meet_link')}")
                self.failed_meetings.add(meeting['id'])
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating meeting: {e}")
            return False

    def check_and_join_meetings(self):
        while True:
            try:
                # Get upcoming meetings in the next hour
                logger.info("Checking for upcoming meetings...")
                meetings = self.calendar_service.get_upcoming_meetings(time_window_minutes=60)
                
                if meetings:
                    logger.info(f"Found {len(meetings)} upcoming meetings")
                    for meeting in meetings:
                        if not self.is_valid_meeting(meeting):
                            continue
                            
                        logger.info(f"Meeting: {meeting['summary']}")
                        logger.info(f"Start time: {meeting['start']}")
                        logger.info(f"Meet link: {meeting['meet_link']}")
                        
                        start_time = datetime.fromisoformat(meeting['start'].replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(meeting['end'].replace('Z', '+00:00'))
                        current_time = datetime.now(pytz.UTC)
                        
                        # Convert all times to UTC for comparison
                        if start_time.tzinfo is None:
                            start_time = pytz.UTC.localize(start_time)
                        if end_time.tzinfo is None:
                            end_time = pytz.UTC.localize(end_time)
                        
                        logger.info(f"Current time (UTC): {current_time}")
                        logger.info(f"Meeting start time (UTC): {start_time}")
                        logger.info(f"Meeting end time (UTC): {end_time}")

                        # Check if it's time to join the meeting (5 minutes before start)
                        if current_time >= start_time - timedelta(minutes=5) and current_time <= end_time:
                            if self.current_meeting != meeting['id']:
                                logger.info(f"Time to join meeting: {meeting['summary']}")
                                
                                # Join the meeting
                                if self.meeting_recorder.join_meeting(meeting['meet_link']):
                                    self.current_meeting = meeting['id']
                                    logger.info(f"Successfully joined meeting: {meeting['summary']}")
                                    
                                    # Start recording in a separate thread
                                    recording_thread = threading.Thread(
                                        target=self.meeting_recorder.start_recording,
                                        args=(meeting['id'],)
                                    )
                                    recording_thread.start()
                                    logger.info("Started recording thread")
                                else:
                                    logger.error(f"Failed to join meeting: {meeting['summary']}")
                                    self.failed_meetings.add(meeting['id'])
                        
                        # Check if current meeting has ended
                        elif self.current_meeting == meeting['id'] and current_time > end_time:
                            logger.info(f"Meeting ended: {meeting['summary']}")
                            self.meeting_recorder.leave_meeting()
                            self.current_meeting = None
                else:
                    logger.info("No upcoming meetings found")

            except Exception as e:
                logger.error(f"Error in meeting manager: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Clear failed meetings list periodically (every hour)
            if len(self.failed_meetings) > 0 and datetime.now().minute == 0:
                self.failed_meetings.clear()
                logger.info("Cleared failed meetings list")
            
            # Check every minute
            time.sleep(60)

def main():
    logger.info("Starting Meet Notes Manager...")
    manager = MeetingManager()
    
    try:
        # Start the meeting manager
        manager.check_and_join_meetings()
    except KeyboardInterrupt:
        logger.info("\nShutting down Meet Notes Manager...")
        if manager.current_meeting:
            manager.meeting_recorder.leave_meeting()

if __name__ == "__main__":
    main() 