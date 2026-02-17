"""
Airflow DAG: Gmail-to-BigQuery Daily Pipeline

Triggers the Cloud Run pipeline service via HTTP POST to /run once per day.

Cloud Composer Setup:
  1. Upload this file to your Composer DAGs bucket:
       gs://<COMPOSER_BUCKET>/dags/gmail_pipeline_dag.py

  2. Create an HTTP connection in the Airflow UI:
       - Conn Id:   gmail_pipeline_cloudrun
       - Conn Type: HTTP
       - Host:      https://<CLOUD_RUN_SERVICE_URL>
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator

default_args = {
    "owner": "airflow",
    "start_date": datetime(2025, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="gmail_to_bigquery_daily",
    default_args=default_args,
    schedule="@daily",
    catchup=False,
    tags=["gmail", "bigquery", "pipeline"],
) as dag:
    trigger_pipeline = SimpleHttpOperator(
        task_id="trigger_gmail_pipeline",
        http_conn_id="gmail_pipeline_cloudrun",
        endpoint="/run",
        method="POST",
        response_check=lambda resp: resp.json().get("status") == "success",
        log_response=True,
    )
