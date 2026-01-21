import os
import base64
import io
import pandas as pd
from datetime import datetime
from flask import Flask
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from pandas_gbq import read_gbq, to_gbq

app = Flask(__name__)

def get_gmail_service():
    if os.path.exists('token.json'):
        # Scopes MUST match what you used to generate the token
        creds = Credentials.from_authorized_user_file('token.json', [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/bigquery'
        ])
        return build('gmail', 'v1', credentials=creds), creds
    raise Exception("token.json missing! Deployment must include this file.")

def run_gmail_to_bigquery_pipeline():
    service, creds = get_gmail_service()
    
    PROJECT_ID = "gmailsync-484911"
    DATASET_ID = "UpworkTest" 
    TABLE_ID = "test-upwork"
    UNIQUE_COL = "timestamp"
    
    today_str = datetime.now().strftime('%Y/%m/%d')
    query = f"after:{today_str} has:attachment filename:csv"
    
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        return "Process complete: No emails found today matching the query."

    all_dfs = []
    for msg in messages:
        message = service.users().messages().get(userId='me', id=msg['id']).execute()
        parts = [message['payload']]
        while parts:
            part = parts.pop()
            if 'parts' in part:
                parts.extend(part['parts'])
            
            if part.get('filename') and part['filename'].lower().endswith('.csv'):
                att_id = part['body']['attachmentId']
                att = service.users().messages().attachments().get(
                    userId='me', messageId=msg['id'], id=att_id).execute()
                
                data = base64.urlsafe_b64decode(att['data'].encode('UTF-8'))
                df = pd.read_csv(io.BytesIO(data))
                all_dfs.append(df)

    if not all_dfs:
        return "Process complete: Emails found, but none contained CSV attachments."

    raw_df = pd.concat(all_dfs).drop_duplicates()

    # --- 3. DEDUPLICATION ---
    try:
        sql = f"SELECT DISTINCT CAST({UNIQUE_COL} AS STRING) as {UNIQUE_COL} FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"
        existing_ids_df = read_gbq(sql, project_id=PROJECT_ID, credentials=creds)
        
        raw_df[UNIQUE_COL] = raw_df[UNIQUE_COL].astype(str).str.strip()
        existing_ids = set(existing_ids_df[UNIQUE_COL].str.strip().tolist())
        final_df = raw_df[~raw_df[UNIQUE_COL].isin(existing_ids)]
    except Exception as e:
        print(f"Deduplication skipped: {e}")
        final_df = raw_df

    # --- 4. LOAD ---
    if not final_df.empty:
        to_gbq(
            final_df, 
            f"{DATASET_ID}.{TABLE_ID}", 
            project_id=PROJECT_ID, 
            if_exists="append",
            credentials=creds
        )
        return f"Pipeline Successful: Uploaded {len(final_df)} new rows to BigQuery."
    
    return "Pipeline Finished: No new data to add (all retrieved rows were already in BigQuery)."

@app.route("/", methods=["GET", "POST"])
def run_endpoint():
    try:
        # Every path in run_gmail_to_bigquery_pipeline now returns a string
        result = run_gmail_to_bigquery_pipeline()
        return result, 200
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(error_details)
        return f"Pipeline Failed: {error_details}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)