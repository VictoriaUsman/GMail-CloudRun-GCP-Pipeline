<img width="1604" height="1030" alt="C5308E27-52ED-4888-8300-BFAA4445CB71" src="https://github.com/user-attachments/assets/7c8f1f36-b7d6-40a5-b391-70de142e4cd0" />


📊 CSV to BigQuery Data Pipeline (GCP + Cloud Run + Power BI)
🚀 Overview

This project demonstrates an end-to-end data ingestion and analytics pipeline built on Google Cloud Platform (GCP).
The pipeline ingests CSV files sent via email, processes them using a Python application running on Cloud Run, loads the data into BigQuery, and finally enables reporting and visualization in Power BI.

This architecture is designed to be serverless, scalable, and cost-efficient, making it ideal for automated batch ingestion use cases.

🏗️ Architecture

Flow:

CSV Files (Email Input)

Users send CSV files (e.g. reports, transactions, logs) via email.

Files are collected and passed to the ingestion service.

Cloud Run (Python Service)

A containerized Python application runs on Cloud Run.

Responsible for:

Validating CSV files

Cleaning and transforming data

Schema alignment

Loading data to BigQuery

BigQuery (Data Warehouse)

Processed data is stored in BigQuery tables.

Optimized for analytics and BI workloads.

Power BI (Analytics & Reporting)

Power BI connects directly to BigQuery.

Dashboards and reports are built on top of curated datasets.

⚙️ Tech Stack
Layer	Technology
Ingestion	CSV via Email
Processing	Python
Compute	Google Cloud Run
Data Warehouse	BigQuery
Visualization	Power BI
Cloud Platform	GCP
🧠 Key Features

✅ Serverless processing (no VM management)

✅ Auto-scaling with Cloud Run

✅ Secure and reliable ingestion

✅ Schema-controlled BigQuery loading

✅ BI-ready datasets

✅ Cost-efficient architecture

📂 Project Structure (Example)
.
├── app/
│   ├── main.py            # Cloud Run entrypoint
│   ├── processor.py       # CSV processing logic
│   ├── bigquery_loader.py # BQ load functions
│   └── utils.py
├── Dockerfile
├── requirements.txt
├── README.md

🔄 Data Processing Logic

Receive CSV file

Validate columns & data types

Clean nulls and bad records

Transform data (if needed)

Load to BigQuery using google-cloud-bigquery

Return success/failure response

🧪 Example Use Cases

Daily sales reports ingestion

Finance data pipelines

Operational metrics ingestion

Automated reporting pipelines

Analytics-ready data for BI tools

🚀 Deployment (Cloud Run)
gcloud builds submit --tag gcr.io/PROJECT_ID/csv-pipeline
gcloud run deploy csv-pipeline \
  --image gcr.io/PROJECT_ID/csv-pipeline \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

📈 Visualization

Power BI connects to BigQuery using:

DirectQuery (real-time dashboards)

Import mode (optimized performance)

🔐 Security Best Practices

Service Account with least-privilege access

BigQuery IAM roles limited to dataset level

Secrets managed via GCP Secret Manager

HTTPS-only Cloud Run endpoint

📝 Future Improvements

Add Cloud Scheduler for automation

Add Pub/Sub for event-driven ingestion

Data quality checks (Great Expectations)

DBT transformations in BigQuery

Partitioned & clustered tables

👨‍💻 Author

Ian Tristan
Aspiring Data Engineer | Cloud & Analytics
GCP • AWS • Azure • Python • SQL • BigQuery • Power BI
