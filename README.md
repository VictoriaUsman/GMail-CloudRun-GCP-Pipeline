<img width="1604" height="1030" alt="C5308E27-52ED-4888-8300-BFAA4445CB71" src="https://github.com/user-attachments/assets/7c8f1f36-b7d6-40a5-b391-70de142e4cd0" />

# Gmail-to-BigQuery Data Pipeline

A serverless data pipeline that extracts CSV attachments from Gmail, deduplicates records, and loads them into BigQuery. Runs on Google Cloud Run with a built-in web dashboard and optional daily scheduling via Apache Airflow (Cloud Composer).

## Architecture

```
Gmail (CSV attachments)
        │
        ▼
  Cloud Run (Flask)  ◄──  Cloud Composer (Airflow DAG)
   POST /run                 @daily schedule
        │
        ▼
    BigQuery
        │
        ▼
    Power BI
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Email Source | Gmail API |
| Compute | Google Cloud Run |
| Orchestration | Apache Airflow (Cloud Composer) |
| Data Warehouse | BigQuery |
| Secrets | GCP Secret Manager |
| Visualization | Power BI |

## Project Structure

```
.
├── main.py                        # Flask app — pipeline logic + dashboard
├── dags/
│   └── gmail_pipeline_dag.py      # Airflow DAG for daily scheduling
├── Dockerfile                     # Cloud Run container
├── requirements.txt               # Python dependencies (Cloud Run)
├── generate_token.py              # One-time Gmail OAuth token generator
└── README.md
```

## How It Works

1. **Trigger** — `POST /run` is called (manually via dashboard, or by Airflow)
2. **Extract** — Queries Gmail for today's emails with CSV attachments
3. **Deduplicate** — Compares incoming rows against existing BigQuery data using the `timestamp` column
4. **Load** — Appends only new rows to BigQuery via `pandas-gbq`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web dashboard with run history and charts |
| `POST` | `/run` | Trigger the pipeline |
| `GET` | `/stats` | Returns BigQuery row count as JSON |

## Setup

### Prerequisites

- GCP project with billing enabled
- Gmail API enabled
- BigQuery dataset and table created
- GCP Secret Manager secret (`gmail-token`) containing OAuth token JSON

### 1. Generate Gmail Token

```bash
python generate_token.py
```

Upload the resulting `token.json` to Secret Manager:

```bash
gcloud secrets create gmail-token --data-file=token.json
```

### 2. Deploy to Cloud Run

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/gmail-pipeline

gcloud run deploy gmail-pipeline \
  --image gcr.io/PROJECT_ID/gmail-pipeline \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### 3. Schedule with Cloud Composer (Optional)

Create a Cloud Composer environment:

```bash
gcloud composer environments create gmail-pipeline-composer \
  --location us-central1 \
  --image-version composer-3-airflow-2.10.2-build.7
```

Upload the DAG:

```bash
DAGS_BUCKET=$(gcloud composer environments describe gmail-pipeline-composer \
  --location us-central1 \
  --format="value(config.dagGcsPrefix)")

gsutil cp dags/gmail_pipeline_dag.py $DAGS_BUCKET/
```

Configure the Airflow HTTP connection:

```bash
gcloud composer environments run gmail-pipeline-composer \
  --location us-central1 \
  connections add -- \
  gmail_pipeline_cloudrun \
  --conn-type http \
  --conn-host "https://<CLOUD_RUN_SERVICE_URL>"
```

> **Note:** Cloud Composer runs a GKE cluster (~$300+/month). For a single daily job, **Cloud Scheduler** is a cheaper alternative (~$0.10/month):
>
> ```bash
> gcloud scheduler jobs create http gmail-pipeline-daily \
>   --location us-central1 \
>   --schedule "0 0 * * *" \
>   --uri "https://<CLOUD_RUN_SERVICE_URL>/run" \
>   --http-method POST \
>   --oidc-service-account-email <SERVICE_ACCOUNT>
> ```

## Configuration

These values are set in `main.py`:

| Variable | Description |
|----------|-------------|
| `PROJECT_ID` | GCP project ID |
| `SECRET_NAME` | Secret Manager secret name for Gmail token |
| `DATASET_ID` | BigQuery dataset |
| `TABLE_ID` | BigQuery table |

## Security

- OAuth token stored in GCP Secret Manager (not in source)
- Cloud Run enforces HTTPS
- Service account with least-privilege IAM roles
- `.dockerignore` excludes credentials from the container image

## Author

**Ian Tristan** — Aspiring Data Engineer | Cloud & Analytics
GCP | AWS | Azure | Python | SQL | BigQuery | Power BI
