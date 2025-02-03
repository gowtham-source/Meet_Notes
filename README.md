# Meet Notes Manager

An automated solution for joining Google Meet meetings and recording meeting content including transcriptions, screen recordings, and audio.

## Features

- Automatic Google Calendar integration
- Automated Google Meet joining
- Screen recording
- Audio recording and real-time transcription
- Timestamp-based organization of recordings
- Persistent browser session to avoid repeated logins

## Prerequisites

- Python 3.8 or higher
- Google Cloud Project with Calendar API enabled
- Chrome browser installed
- Working microphone for audio recording

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Google Cloud Project:
   - Go to Google Cloud Console
   - Create a new project
   - Enable Google Calendar API
   - Create OAuth 2.0 credentials
   - Download the credentials and save as `credentials.json` in the project root

3. First-time setup:
   - Run the application once: `python main.py`
   - Follow the OAuth consent flow in your browser
   - The application will save the token for future use

## Usage

Simply run the main script:
```bash
python main.py
```

The application will:
1. Monitor your Google Calendar for upcoming meetings
2. Join meetings automatically 5 minutes before start time
3. Record screen and audio
4. Generate transcriptions with timestamps
5. Save all recordings in the `recordings` directory

## Output Structure

```
recordings/
├── meeting_id_timestamp/
│   ├── screen_recording.avi
│   └── transcription.txt
```

## Notes

- The application uses a persistent Chrome profile to maintain login state
- Recordings are organized by meeting ID and timestamp
- The application checks for new meetings every minute
- Press Ctrl+C to safely exit the application

## Troubleshooting

1. If you encounter authentication issues:
   - Delete `token.json` and restart the application
   - Go through the OAuth consent flow again

2. If the browser automation fails:
   - Clear the Chrome profile directory
   - Ensure Chrome is updated to the latest version 