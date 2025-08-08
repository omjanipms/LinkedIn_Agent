# LinkedIn Post Generator Agent

This AI agent automatically generates and posts content to LinkedIn based on topics provided in a Google Sheet.

## Features

- Reads topics from a Google Sheet
- Generates engaging content using Google's Gemini Pro
- Finds relevant images for each topic
- Posts content directly to LinkedIn
- Updates the Google Sheet with generated content and image paths

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Google Sheets API:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Sheets API
   - Create credentials (OAuth 2.0 Client ID)
   - Download the credentials and save as `credentials.json` in the project root

3. Create a `.env` file in the project root with the following variables:
```
GOOGLE_API_KEY=your_google_api_key
LINKEDIN_EMAIL=your_linkedin_email
LINKEDIN_PASSWORD=your_linkedin_password
UNSPLASH_ACCESS_KEY=your_unsplash_api_key
SPREADSHEET_ID=your_google_sheet_id
```

4. Prepare your Google Sheet with the following columns:
   - topic: The main topic for the post
   - content: (Leave empty, will be filled by the agent)
   - image: (Leave empty, will be filled by the agent)

## Usage

1. Add your topics to the Google Sheet
2. Run the agent:
```bash
python linkedin_agent.py
```

The agent will:
- Read topics from the Google Sheet
- Generate content for each topic using Gemini Pro
- Find relevant images
- Post to LinkedIn
- Update the Google Sheet with the generated content and image paths

## Notes

- The agent will only process topics that don't have content or images yet
- There's a 5-second delay between posts to avoid rate limiting
- Make sure your LinkedIn account has the necessary permissions to post
- The image search functionality requires an Unsplash API key
- Content is generated using Google's Gemini Pro model, which is optimized for professional content creation
- First time running the script will open a browser window for Google authentication

## Requirements

- Python 3.7+
- Google API key (for Gemini)
- Google Sheets API credentials
- LinkedIn account
- Unsplash API key (for image search) 