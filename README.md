<img width="1604" height="1030" alt="C5308E27-52ED-4888-8300-BFAA4445CB71" src="https://github.com/user-attachments/assets/7c8f1f36-b7d6-40a5-b391-70de142e4cd0" />

# Gmail-to-BigQuery Data Pipeline

A serverless data pipeline that extracts CSV attachments from Gmail, deduplicates records, and loads them into BigQuery. Runs on Google Cloud Run with a built-in web dashboard and optional daily scheduling via Apache Airflow (Cloud Composer).

## Architecture

```
Gmail (CSV attachments)
        |
        v
  Cloud Run (Flask)  <--  Cloud Composer / Airflow DAG
   POST /run                 @daily schedule
        |
        v
    BigQuery
        |
        v
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
├── docker-compose.yaml            # Local dev: Airflow + pipeline service
├── requirements.txt               # Python dependencies
├── generate_token.py              # One-time Gmail OAuth token generator
├── .env.example                   # Environment variable template
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

## Environment Variables

All configuration is driven by environment variables (with sensible defaults):

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | GCP project ID | `donkee-473801` |
| `SECRET_NAME` | Secret Manager secret name for Gmail token | `gmail-token` |
| `BQ_DATASET_ID` | BigQuery dataset | `UpworkTest` |
| `BQ_TABLE_ID` | BigQuery table | `test-upwork` |
| `UNIQUE_COL` | Column used for deduplication | `timestamp` |
| `PORT` | Server port (set automatically on Cloud Run) | `8080` |

Copy `.env.example` to `.env` and fill in your values for local development.

---

## Local Development with Docker Compose

The `docker-compose.yaml` runs the full stack locally: the Flask pipeline service **and** a local Airflow instance (webserver + scheduler + PostgreSQL).

### Prerequisites

- Docker and Docker Compose installed
- A GCP service account key (`service-account.json`) with access to Gmail API, BigQuery, and Secret Manager

### Quick Start

```bash
# 1. Copy and configure environment variables
cp .env.example .env
# Edit .env with your GCP project details

# 2. Place your service account key in the project root
cp /path/to/your/service-account.json ./service-account.json

# 3. Start all services
docker compose up --build
```

### Services

| Service | URL | Description |
|---------|-----|-------------|
| Pipeline Dashboard | http://localhost:8080 | Flask app — run pipeline, view stats |
| Airflow Webserver | http://localhost:8081 | DAG management (admin / admin) |
| PostgreSQL | localhost:5432 | Airflow metadata database |

### Running Individual Services

```bash
# Pipeline only (no Airflow)
docker compose up pipeline --build

# Airflow only (assumes pipeline is deployed elsewhere)
docker compose up postgres airflow-init airflow-webserver airflow-scheduler
```

### Configure Airflow HTTP Connection (Local)

After Airflow starts, create the HTTP connection so the DAG can reach the local pipeline:

1. Open http://localhost:8081 (admin / admin)
2. Go to **Admin > Connections**
3. Add a new connection:
   - **Conn Id:** `gmail_pipeline_cloudrun`
   - **Conn Type:** HTTP
   - **Host:** `http://pipeline:8080`

The DAG `gmail_to_bigquery_daily` will now trigger the pipeline container on its `@daily` schedule.

---

## Cloud Deployment

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
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=PROJECT_ID,BQ_DATASET_ID=your_dataset,BQ_TABLE_ID=your_table"
```

### 3. Schedule with Cloud Composer

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

### Alternative: Cloud Scheduler (Cheaper)

> Cloud Composer runs a GKE cluster (~$300+/month). For a single daily job, **Cloud Scheduler** is a much cheaper alternative (~$0.10/month):
>
> ```bash
> gcloud scheduler jobs create http gmail-pipeline-daily \
>   --location us-central1 \
>   --schedule "0 0 * * *" \
>   --uri "https://<CLOUD_RUN_SERVICE_URL>/run" \
>   --http-method POST \
>   --oidc-service-account-email <SERVICE_ACCOUNT>
> ```

---

## Security

- OAuth token stored in GCP Secret Manager (not in source)
- Cloud Run enforces HTTPS
- Service account with least-privilege IAM roles
- `.dockerignore` excludes credentials from the container image
- `.gitignore` excludes `.env`, `service-account.json`, and credential files

## Author

**Ian Tristan** — Aspiring Data Engineer | Cloud & Analytics
GCP | AWS | Azure | Python | SQL | BigQuery | Power BI
