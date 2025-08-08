import os
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import sys
import traceback
import json
from requests_oauthlib import OAuth2Session
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.parse

# Allow insecure transport for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

class LinkedInAgent:
    def __init__(self):
        try:
            print("Initializing LinkedIn Agent...")
            load_dotenv()
            
            # Verify environment variables
            self.api_key = os.getenv('GOOGLE_API_KEY')
            print(f"GOOGLE_API_KEY found: {bool(self.api_key)}")
            
            # LinkedIn OAuth2 credentials
            self.linkedin_client_id = os.getenv('LINKEDIN_CLIENT_ID')
            self.linkedin_client_secret = os.getenv('LINKEDIN_CLIENT_SECRET')
            self.redirect_uri = 'http://localhost:8080/callback'  # Using HTTP for local development
            print(f"LINKEDIN OAuth credentials found: {bool(self.linkedin_client_id and self.linkedin_client_secret)}")
            
            self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
            print(f"SPREADSHEET_ID found: {bool(self.spreadsheet_id)}")
            
            if not all([self.api_key, self.linkedin_client_id, self.linkedin_client_secret, self.spreadsheet_id]):
                raise ValueError("Missing required environment variables")
            
            print("Configuring Gemini...")
            genai.configure(api_key=self.api_key)
            
            # List available models
            print("Available models:")
            for model in genai.list_models():
                print(f"- {model.name}")
            
            # Use the correct model name from available models
            model_name = 'models/gemini-1.5-pro'
            self.model = genai.GenerativeModel(model_name)
            print(f"Using model: {model_name}")
            
            # Initialize LinkedIn connection
            print("Initializing LinkedIn connection...")
            self.linkedin_token = self.load_linkedin_token()
            if not self.linkedin_token:
                self.linkedin_token = self.get_linkedin_token()
            
            self.service = None
            print("Initialization successful!")
            
        except Exception as e:
            print(f"Error during initialization: {e}")
            print("Traceback:")
            traceback.print_exc()
            sys.exit(1)

    def get_linkedin_token(self):
        """Get LinkedIn OAuth2 token."""
        try:
            print("\nStarting LinkedIn authentication process...")
            print(f"Client ID: {self.linkedin_client_id}")
            print(f"Redirect URI: {self.redirect_uri}")
            
            # Verify client credentials
            if not self.linkedin_client_id or not self.linkedin_client_secret:
                print("Error: LinkedIn client credentials are missing")
                print("Please check your .env file and ensure LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET are set")
                return None

            # Define the OAuth2 session with required scopes
            oauth = OAuth2Session(
                client_id=self.linkedin_client_id,
                redirect_uri=self.redirect_uri,
                scope=['openid', 'profile', 'email', 'w_member_social']
            )

            # Create a simple HTTP server to handle the callback
            class CallbackHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    print(f"\nReceived callback request: {self.path}")
                    if self.path.startswith('/callback'):
                        query = urllib.parse.urlparse(self.path).query
                        params = urllib.parse.parse_qs(query)
                        print(f"Callback parameters: {params}")
                        
                        if 'code' in params:
                            self.server.auth_code = params['code'][0]
                            print("Authorization code received successfully")
                            self.send_response(200)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            self.wfile.write(b'Authentication successful! You can close this window.')
                        elif 'error' in params:
                            error = params['error'][0]
                            error_description = params.get('error_description', [''])[0]
                            print(f"\nAuthorization error: {error}")
                            print(f"Error description: {error_description}")
                            if error == 'access_denied':
                                print("\nYou denied access to the application. Please try again and authorize the application.")
                            elif error == 'invalid_scope':
                                print("\nInvalid scope requested. Please check your LinkedIn app settings.")
                            self.send_response(400)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            self.wfile.write(b'Authentication failed! Please check the console for details.')
                        else:
                            print("\nNo authorization code or error received in callback")
                            self.send_response(400)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            self.wfile.write(b'Authentication failed!')
                    else:
                        print(f"\nInvalid callback path: {self.path}")
                        self.send_response(404)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b'Not found')

            # Start local server to receive the callback
            print("\nStarting local server to receive callback...")
            server = HTTPServer(('localhost', 8080), CallbackHandler)
            server.auth_code = None

            # Get the authorization URL
            print("\nGenerating authorization URL...")
            authorization_url, _ = oauth.authorization_url(
                'https://www.linkedin.com/oauth/v2/authorization',
                state='random_state_string'
            )

            # Open the authorization URL in a browser
            print("\nPlease follow these steps:")
            print("1. A browser window will open with the LinkedIn authorization page")
            print("2. Log in to your LinkedIn account if not already logged in")
            print("3. Authorize the application")
            print("4. You will be redirected back to the application")
            print("\nIf the browser doesn't open automatically, please visit this URL:")
            print(authorization_url)
            print("\nWaiting for authorization...")
            
            webbrowser.open(authorization_url)

            # Wait for the callback
            print("\nWaiting for callback from LinkedIn...")
            while server.auth_code is None:
                server.handle_request()

            if not server.auth_code:
                print("\nAuthentication failed: No authorization code received")
                print("Please check if you authorized the application in the browser")
                return None

            print("\nAuthorization code received, exchanging for access token...")

            # Exchange the authorization code for a token
            token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
            data = {
                'grant_type': 'authorization_code',
                'code': server.auth_code,
                'redirect_uri': self.redirect_uri,
                'client_id': self.linkedin_client_id,
                'client_secret': self.linkedin_client_secret
            }
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            print("\nSending token request to LinkedIn...")
            response = requests.post(token_url, data=data, headers=headers)
            
            if response.status_code != 200:
                print(f"\nError getting access token: {response.status_code}")
                print(f"Response: {response.text}")
                print("\nPossible causes:")
                print("1. Invalid client credentials")
                print("2. Authorization code expired")
                print("3. Incorrect redirect URI")
                print("4. Missing or incorrect OAuth scopes")
                return None

            token = response.json()
            print("\nSuccessfully obtained access token!")

            # Get the user's profile information using the new API endpoint
            headers = {
                'Authorization': f'Bearer {token["access_token"]}',
                'X-Restli-Protocol-Version': '2.0.0'
            }
            
            print("\nFetching LinkedIn profile information...")
            profile_response = requests.get('https://api.linkedin.com/v2/userinfo', headers=headers)
            
            if profile_response.status_code == 200:
                profile = profile_response.json()
                token['linkedin_id'] = profile['sub']  # Using 'sub' as the user ID
                print(f"Successfully retrieved LinkedIn profile ID: {profile['sub']}")
                
                # Save the token for later use
                with open('linkedin_token.json', 'w') as f:
                    json.dump(token, f)
                print("LinkedIn token saved successfully")
                return token
            else:
                print(f"\nFailed to get LinkedIn profile: {profile_response.status_code}")
                print(f"Response: {profile_response.text}")
                print("\nPlease check if you have the correct permissions set in your LinkedIn app settings")
                print("Required permissions:")
                print("1. openid")
                print("2. profile")
                print("3. email")
                print("4. w_member_social")
                return None

        except Exception as e:
            print(f"\nError during LinkedIn authentication: {str(e)}")
            print("Traceback:")
            traceback.print_exc()
            return None
        finally:
            server.server_close()

    def load_linkedin_token(self):
        """Load LinkedIn token from file if it exists."""
        try:
            if os.path.exists('linkedin_token.json'):
                with open('linkedin_token.json', 'r') as f:
                    token = json.load(f)
                    # Check if token is expired
                    if time.time() < token.get('expires_at', 0):
                        print("Using existing valid LinkedIn token")
                        return token
                    else:
                        print("LinkedIn token expired")
                        return None
            return None
        except Exception as e:
            print(f"Error loading LinkedIn token: {str(e)}")
            return None

    def get_google_sheets_service(self):
        """Get Google Sheets service with proper authentication"""
        try:
            print("Setting up Google Sheets service...")
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
            creds = None
            
            if os.path.exists('token.pickle'):
                print("Found existing token.pickle file")
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                print("No valid credentials found, starting OAuth flow...")
                if creds and creds.expired and creds.refresh_token:
                    print("Refreshing expired credentials...")
                    creds.refresh(Request())
                else:
                    if not os.path.exists('credentials.json'):
                        raise FileNotFoundError("credentials.json not found. Please download it from Google Cloud Console")
                    print("Starting OAuth flow...")
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                print("Saving credentials...")
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            
            print("Building Google Sheets service...")
            self.service = build('sheets', 'v4', credentials=creds)
            print("Successfully connected to Google Sheets")
            
        except Exception as e:
            print(f"Error connecting to Google Sheets: {e}")
            print("Traceback:")
            traceback.print_exc()
            sys.exit(1)

    def read_spreadsheet(self):
        """Read the Google Sheet containing topics"""
        try:
            print("Reading spreadsheet...")
            if not self.service:
                self.get_google_sheets_service()
            
            print(f"Accessing spreadsheet ID: {self.spreadsheet_id}")
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:C'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                print("No data found in the spreadsheet")
                return []
            
            print(f"Found {len(values)} rows in spreadsheet")
            # Convert to list of dictionaries
            headers = values[0]
            print("Headers:", headers)  # Debugging line to check headers
            data = []
            for row in values[1:]:
                data.append(dict(zip(headers, row)))
            print(f"Successfully read {len(data)} rows from spreadsheet")
            print("Data structure:", data)  # Debugging line to check data structure
            return data
            
        except Exception as e:
            print(f"Error reading spreadsheet: {e}")
            print("Traceback:")
            traceback.print_exc()
            sys.exit(1)

    def find_image(self, topic):
        """Find and download an image related to the topic from Unsplash"""
        try:
            print(f"Finding image for topic: {topic}")
            unsplash_access_key = os.getenv('UNSPLASH_ACCESS_KEY')
            if not unsplash_access_key:
                print("UNSPLASH_ACCESS_KEY not found in .env file")
                return None
                
            url = f"https://api.unsplash.com/photos/random?query={topic}&client_id={unsplash_access_key}"
            print(f"Requesting image from Unsplash...")
            response = requests.get(url)
            if response.status_code == 200:
                image_url = response.json()['urls']['regular']
                print(f"Successfully found image URL: {image_url}")
                return image_url
            print(f"Failed to find image. Status code: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"Error finding image: {e}")
            print("Traceback:")
            traceback.print_exc()
            return None

    def generate_content(self, topic: str) -> str:
        """Generate content for a given topic using Gemini."""
        try:
            # Define emoji mappings for different topics
            emoji_mapping = {
                'technology': '🚀',
                'marketing': '📊',
                'ai': '🤖',
                'machine learning': '🧠',
                'cyber security': '🔒',
                'network': '🌐',
                'data': '📈',
                'business': '💼',
                'development': '💻',
                'cloud': '☁️',
                'blockchain': '⛓️',
                'iot': '📱',
                'automation': '⚙️',
                'analytics': '📊',
                'innovation': '💡'
            }

            # Determine the most relevant emoji for the topic
            topic_lower = topic.lower()
            emoji = '💡'  # Default emoji
            for key, value in emoji_mapping.items():
                if key in topic_lower:
                    emoji = value
                    break

            prompt = f"""Generate a professional LinkedIn post about {topic}. 
            The post should:
            1. Start with an engaging hook using {emoji}
            2. Include 2-3 key points about the topic
            3. Use relevant emojis for each section
            4. End with a call to action
            5. Include relevant hashtags
            6. Keep the tone professional but engaging
            7. Format the topic name in bold
            8. Ensure the content is accurate and informative
            9. Use proper spacing and formatting
            10. Keep the post under 2500 characters to account for emojis and formatting
            
            Example format:
            {emoji} **Topic Name**
            
            [Brief engaging introduction - 1-2 sentences]
            
            🔑 Key Point 1
            [Concise explanation - 2-3 sentences]
            
            💡 Key Point 2
            [Concise explanation - 2-3 sentences]
            
            [Call to action - 1 sentence]
            
            #RelevantHashtags #MoreHashtags"""

            response = self.model.generate_content(prompt)
            content = response.text
            
            # Ensure content is within LinkedIn's limit
            if len(content) > 2500:
                content = content[:2500] + "...\n\n#LinkedInPost"
            
            return content
        except Exception as e:
            print(f"Error generating content: {str(e)}")
            return f"Error generating content for {topic}"

    def update_spreadsheet_row(self, row_index, content, image_url):
        """Update a specific row in the spreadsheet with new content and image URL"""
        try:
            print(f"Updating spreadsheet row {row_index}...")
            if not self.service:
                self.get_google_sheets_service()
            
            range_name = f'Sheet1!B{row_index+1}:C{row_index+1}'  # +1 because spreadsheet is 1-indexed
            values = [[content, image_url]]
            
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            print(f"Successfully updated spreadsheet row {row_index}")
            return True
            
        except Exception as e:
            print(f"Error updating spreadsheet: {e}")
            print("Traceback:")
            traceback.print_exc()
            return False

    def post_to_linkedin(self, topic, content, image_url):
        """Post content to LinkedIn."""
        if not self.linkedin_token:
            print("Cannot post to LinkedIn: No valid token")
            return False

        try:
            print("Preparing LinkedIn post...")
            
            # Clean the content by removing '*' and extra whitespace
            cleaned_content = content.replace('*', '').strip()
            
            # Download the image
            print(f"Downloading image from URL: {image_url}")
            image_response = requests.get(image_url)
            if image_response.status_code != 200:
                print(f"Failed to download image: {image_response.status_code}")
                return False

            # Save the image temporarily
            with open('temp_image.jpg', 'wb') as f:
                f.write(image_response.content)

            # Register the image upload
            print("Registering image upload...")
            register_upload_url = 'https://api.linkedin.com/v2/assets?action=registerUpload'
            register_upload_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": f"urn:li:person:{self.linkedin_token['linkedin_id']}",
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }

            headers = {
                'Authorization': f'Bearer {self.linkedin_token["access_token"]}',
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0'
            }

            register_response = requests.post(register_upload_url, headers=headers, json=register_upload_data)
            if register_response.status_code != 200:
                print(f"Failed to register upload: {register_response.status_code}")
                print(f"Response: {register_response.text}")
                return False

            upload_url = register_response.json()['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
            asset = register_response.json()['value']['asset']

            # Upload the image
            print("Uploading image...")
            with open('temp_image.jpg', 'rb') as f:
                upload_response = requests.put(upload_url, data=f.read())
                if upload_response.status_code != 201:
                    print(f"Failed to upload image: {upload_response.status_code}")
                    return False

            # Create the post with image
            print("Creating LinkedIn post with image...")
            post_data = {
                "author": f"urn:li:person:{self.linkedin_token['linkedin_id']}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": f"{topic}\n\n{cleaned_content}"
                        },
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": topic
                                },
                                "media": asset,
                                "title": {
                                    "text": topic
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            response = requests.post(
                'https://api.linkedin.com/v2/ugcPosts',
                headers=headers,
                json=post_data
            )

            if response.status_code != 201:
                print(f"Failed to create post: {response.status_code}")
                print(f"Response: {response.text}")
                return False

            print("Successfully posted to LinkedIn!")
            print("Post URL:", response.headers.get('x-restli-id'))
            
            # Clean up temporary file
            try:
                os.remove('temp_image.jpg')
            except:
                pass
                
            return True

        except Exception as e:
            print(f"Error posting to LinkedIn: {str(e)}")
            print("Traceback:")
            import traceback
            print(traceback.format_exc())
            return False

    def process_spreadsheet_and_post(self):
        """Process spreadsheet data and post to LinkedIn"""
        try:
            # Read spreadsheet data
            sheet = self.service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:C'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                print("No data found in spreadsheet")
                return
            
            print("\nCurrent spreadsheet data:")
            for i, row in enumerate(values):
                print(f"Row {i+1}: {row}")
            
            # Find the most recent row without content
            last_row_without_content = None
            for i in range(len(values)-1, 0, -1):  # Start from the last row and go up
                row = values[i]
                if len(row) < 2 or not row[1]:  # Check if content is missing
                    last_row_without_content = row
                    break
            
            if not last_row_without_content:
                print("\nNo new topics found to process")
                return
            
            topic = last_row_without_content[0].strip()
            if not topic:
                print("\nError: Topic name is missing in the row")
                return
            
            print(f"\nProcessing post for topic: {topic}")
            
            # Generate content
            print(f"Generating content for topic: {topic}")
            content = self.generate_content(topic)
            if not content:
                print(f"Failed to generate content for topic: {topic}")
                return
            
            # Find image
            print(f"Finding image for topic: {topic}")
            image_url = self.find_image(topic)
            if not image_url:
                print(f"Failed to find image for topic: {topic}")
                return
            
            # Update spreadsheet with new content and image
            row_index = values.index(last_row_without_content)
            print(f"Updating spreadsheet row {row_index + 1}...")
            update_range = f'Sheet1!B{row_index + 1}:C{row_index + 1}'
            update_values = [[content, image_url]]
            body = {
                'values': update_values
            }
            result = sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=update_range,
                valueInputOption='RAW',
                body=body
            ).execute()
            print("Successfully updated spreadsheet with content and image URL")
            
            # Verify the update
            result = sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'Sheet1!A{row_index + 1}:C{row_index + 1}'
            ).execute()
            updated_row = result.get('values', [[]])[0]
            print("\nUpdated row data:")
            print(f"Topic: {updated_row[0]}")
            print(f"Content: {updated_row[1][:100]}...")  # Show first 100 chars of content
            print(f"Image URL: {updated_row[2]}")
            
            # Post to LinkedIn
            print("\nPreparing LinkedIn post...")
            success = self.post_to_linkedin(topic, content, image_url)
            if success:
                print(f"Successfully posted content for topic: {topic}")
            else:
                print(f"Failed to post content for topic: {topic}")
            
        except Exception as e:
            print(f"Error processing spreadsheet: {str(e)}")
            traceback.print_exc()

    def run(self):
        """Main execution method"""
        try:
            print("Starting LinkedIn Post Generator...")
            
            # Get Google Sheets service
            self.get_google_sheets_service()
            
            # Process spreadsheet and post content
            self.process_spreadsheet_and_post()
            
            print("\nAll posts processed successfully!")
            
        except Exception as e:
            print(f"Error in main execution: {e}")
            print("Traceback:")
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    agent = LinkedInAgent()
    agent.run() 