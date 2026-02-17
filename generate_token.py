"""
Local-only script to generate token.json via OAuth consent flow.
Run this once locally, then upload token.json to Secret Manager.

Usage:
    1. Place credentials.json (OAuth Client ID) in this directory
    2. Run: python generate_token.py
    3. Complete the OAuth consent in your browser
    4. token.json will be saved in this directory
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/bigquery',
]

def main():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)

    with open('token.json', 'w') as f:
        f.write(creds.to_json())

    print("token.json saved successfully.")

if __name__ == '__main__':
    main()
