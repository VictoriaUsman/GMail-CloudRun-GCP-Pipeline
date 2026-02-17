import os
import json
import base64
import io
import traceback
import pandas as pd
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.cloud import secretmanager
from pandas_gbq import read_gbq, to_gbq

app = Flask(__name__)

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "donkee-473801")
SECRET_NAME = os.environ.get("SECRET_NAME", "gmail-token")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "UpworkTest")
TABLE_ID = os.environ.get("BQ_TABLE_ID", "test-upwork")
UNIQUE_COL = os.environ.get("UNIQUE_COL", "timestamp")

# In-memory run log (last 20 runs)
run_log = []

def get_gmail_service():
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    token_data = json.loads(response.payload.data.decode("UTF-8"))

    creds = Credentials.from_authorized_user_info(token_data, [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/bigquery',
    ])
    return build('gmail', 'v1', credentials=creds), creds

def get_bq_row_count():
    """Query BigQuery for the total row count."""
    try:
        _, creds = get_gmail_service()
        sql = f"SELECT COUNT(*) as cnt FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"
        df = read_gbq(sql, project_id=PROJECT_ID, credentials=creds)
        return int(df['cnt'].iloc[0])
    except Exception as e:
        print(f"Could not fetch BQ row count: {e}")
        return None

def run_gmail_to_bigquery_pipeline():
    service, creds = get_gmail_service()

    today_str = datetime.now().strftime('%Y/%m/%d')
    query = f"after:{today_str} has:attachment filename:csv"

    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        return {"status": "success", "rows_uploaded": 0,
                "message": "No emails found today matching the query."}

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
        return {"status": "success", "rows_uploaded": 0,
                "message": "Emails found, but none contained CSV attachments."}

    raw_df = pd.concat(all_dfs).drop_duplicates()

    # --- DEDUPLICATION ---
    try:
        sql = f"SELECT DISTINCT CAST({UNIQUE_COL} AS STRING) as {UNIQUE_COL} FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"
        existing_ids_df = read_gbq(sql, project_id=PROJECT_ID, credentials=creds)

        raw_df[UNIQUE_COL] = raw_df[UNIQUE_COL].astype(str).str.strip()
        existing_ids = set(existing_ids_df[UNIQUE_COL].str.strip().tolist())
        final_df = raw_df[~raw_df[UNIQUE_COL].isin(existing_ids)]
    except Exception as e:
        print(f"Deduplication skipped: {e}")
        final_df = raw_df

    # --- LOAD ---
    if not final_df.empty:
        to_gbq(
            final_df,
            f"{DATASET_ID}.{TABLE_ID}",
            project_id=PROJECT_ID,
            if_exists="append",
            credentials=creds
        )
        return {"status": "success", "rows_uploaded": len(final_df),
                "message": f"Uploaded {len(final_df)} new rows to BigQuery."}

    return {"status": "success", "rows_uploaded": 0,
            "message": "No new data to add (all rows already in BigQuery)."}

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gmail Pipeline Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }
  h1 { font-size: 1.5rem; margin-bottom: 1.5rem; color: #f8fafc; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
           gap: 1rem; margin-bottom: 1.5rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.25rem;
          border: 1px solid #334155; }
  .card .label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
                 color: #94a3b8; margin-bottom: 0.5rem; }
  .card .value { font-size: 1.75rem; font-weight: 700; }
  .card .value.success { color: #4ade80; }
  .card .value.neutral { color: #60a5fa; }
  .card .value.error { color: #f87171; }
  .chart-wrap { background: #1e293b; border-radius: 10px; padding: 1.25rem;
                border: 1px solid #334155; margin-bottom: 1.5rem; max-height: 300px; }
  .actions { margin-bottom: 1.5rem; }
  .btn { background: #3b82f6; color: #fff; border: none; padding: 0.65rem 1.5rem;
         border-radius: 8px; font-size: 0.9rem; cursor: pointer; font-weight: 600; }
  .btn:hover { background: #2563eb; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .log-panel { background: #1e293b; border-radius: 10px; padding: 1.25rem;
               border: 1px solid #334155; max-height: 320px; overflow-y: auto; }
  .log-panel h2 { font-size: 1rem; margin-bottom: 0.75rem; color: #f8fafc; }
  .log-entry { padding: 0.5rem 0; border-bottom: 1px solid #334155;
               font-size: 0.85rem; line-height: 1.5; }
  .log-entry:last-child { border-bottom: none; }
  .log-entry .ts { color: #64748b; margin-right: 0.75rem; }
  .log-entry .rows { color: #4ade80; font-weight: 600; }
  .log-entry .msg { color: #cbd5e1; }
  .log-entry.error .msg { color: #f87171; }
  .empty { color: #64748b; font-style: italic; }
</style>
</head>
<body>
<h1>Gmail &rarr; BigQuery Pipeline</h1>

<div class="cards">
  <div class="card">
    <div class="label">BigQuery Rows</div>
    <div class="value neutral" id="bq-rows">&mdash;</div>
  </div>
  <div class="card">
    <div class="label">Last Upload</div>
    <div class="value success" id="last-upload">&mdash;</div>
  </div>
  <div class="card">
    <div class="label">Last Status</div>
    <div class="value neutral" id="last-status">&mdash;</div>
  </div>
</div>

<div class="chart-wrap">
  <canvas id="chart"></canvas>
</div>

<div class="actions">
  <button class="btn" id="run-btn" onclick="runPipeline()">Run Pipeline</button>
</div>

<div class="log-panel">
  <h2>Run Log</h2>
  <div id="log-list"><span class="empty">No runs yet.</span></div>
</div>

<script>
const chartCtx = document.getElementById('chart').getContext('2d');
const chart = new Chart(chartCtx, {
  type: 'bar',
  data: { labels: [], datasets: [{
    label: 'Rows Uploaded',
    data: [],
    backgroundColor: '#3b82f6',
    borderRadius: 4
  }]},
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#94a3b8' } } },
    scales: {
      x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
      y: { beginAtZero: true, ticks: { color: '#64748b', precision: 0 }, grid: { color: '#334155' } }
    }
  }
});

let logData = {{ log_data | tojson }};

function refreshUI() {
  // Update log list
  const logEl = document.getElementById('log-list');
  if (logData.length === 0) {
    logEl.innerHTML = '<span class="empty">No runs yet.</span>';
  } else {
    logEl.innerHTML = logData.map(e =>
      `<div class="log-entry ${e.status === 'error' ? 'error' : ''}">
         <span class="ts">${e.timestamp}</span>
         <span class="rows">+${e.rows_uploaded} rows</span>
         <span class="msg">${e.message}</span>
       </div>`
    ).join('');
  }

  // Update chart
  chart.data.labels = logData.map(e => e.timestamp.split(' ')[1] || e.timestamp);
  chart.data.datasets[0].data = logData.map(e => e.rows_uploaded);
  chart.update();

  // Update cards from last entry
  if (logData.length > 0) {
    const last = logData[logData.length - 1];
    document.getElementById('last-upload').textContent = last.rows_uploaded + ' rows';
    const statusEl = document.getElementById('last-status');
    statusEl.textContent = last.status;
    statusEl.className = 'value ' + (last.status === 'error' ? 'error' : 'success');
  }
}

async function fetchStats() {
  try {
    const res = await fetch('/stats');
    const data = await res.json();
    document.getElementById('bq-rows').textContent =
      data.total_rows !== null ? data.total_rows.toLocaleString() : 'N/A';
  } catch(e) {
    document.getElementById('bq-rows').textContent = 'Error';
  }
}

async function runPipeline() {
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.textContent = 'Running...';
  try {
    const res = await fetch('/run', { method: 'POST' });
    const data = await res.json();
    logData.push(data);
    refreshUI();
    fetchStats();
  } catch(e) {
    logData.push({ timestamp: new Date().toLocaleString(), status: 'error',
                   rows_uploaded: 0, message: 'Request failed: ' + e.message });
    refreshUI();
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run Pipeline';
  }
}

refreshUI();
fetchStats();
</script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def dashboard():
    return render_template_string(DASHBOARD_HTML, log_data=run_log)

@app.route("/run", methods=["POST"])
def run_pipeline():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        result = run_gmail_to_bigquery_pipeline()
        entry = {"timestamp": ts, "status": result["status"],
                 "rows_uploaded": result["rows_uploaded"],
                 "message": result["message"]}
    except Exception as e:
        error_details = traceback.format_exc()
        print(error_details)
        entry = {"timestamp": ts, "status": "error",
                 "rows_uploaded": 0, "message": str(e)}

    run_log.append(entry)
    if len(run_log) > 20:
        run_log.pop(0)

    return jsonify(entry)

@app.route("/stats", methods=["GET"])
def stats():
    total_rows = get_bq_row_count()
    return jsonify({"total_rows": total_rows, "table": f"{DATASET_ID}.{TABLE_ID}"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
