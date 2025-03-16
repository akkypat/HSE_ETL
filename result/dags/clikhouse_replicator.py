from email.policy import default
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import psycopg2
import logging
from lib import default_args, ch_client, pg_conn


def create_tables() -> None:
    """
    CREATE TABLE IF NOT EXISTS user_activity_daily (
        date Date,
        user_id UInt32,
        sessions UInt32,
        page_views UInt32
    ) ENGINE = MergeTree()
    ORDER BY (date, user_id)
    """

    """
        CREATE TABLE IF NOT EXISTS support_performance (
            day DateTime,
            status String,
            ticket_count UInt32,
            avg_resolution_time Float32
        ) ENGINE = MergeTree()
        ORDER BY (day, status)
    """

    """
        CREATE TABLE activity_tickets (
            user_id UInt32,
            last_session_date Date,
            total_sessions UInt32,
            tickets_count UInt32,
            avg_response_time Float32
        ) ENGINE = MergeTree()
        ORDER BY (user_id, last_session_date)
    """


def transfer_data() -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                DATE(start_time) AS date,
                user_id,
                COUNT(*) AS sessions,
                SUM(JSONB_ARRAY_LENGTH(pages_visited)) AS page_views
            FROM replicated_data.user_sessions
            GROUP BY date, user_id
        """)

        ch_client.execute(
            "INSERT INTO user_activity_daily VALUES",
            [(row[0], row[1], row[2], row[3]) for row in cursor.fetchall()],
        )

        cursor.execute("""
            SELECT 
                DATE_TRUNC('day', created_at) AS day,
                status,
                COUNT(*) AS ticket_count,
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) AS avg_time
            FROM replicated_data.support_tickets
            GROUP BY day, status
        """)

        ch_client.execute(
            "INSERT INTO support_performance VALUES",
            [(row[0], row[1], row[2], row[3]) for row in cursor.fetchall()],
        )

        cursor.execute("""
            SELECT
                u.user_id,
                MAX(DATE(u.start_time)) AS last_active,
                COUNT(DISTINCT u.session_id) AS sessions,
                COUNT(t.ticket_id) AS tickets,
                coalesce(AVG(EXTRACT(EPOCH FROM (t.updated_at - t.created_at))), -1) AS avg_response
            FROM replicated_data.user_sessions u
            LEFT JOIN replicated_data.support_tickets t ON u.user_id = t.user_id
            GROUP BY u.user_id
    """)

        ch_client.execute(
            "INSERT INTO activity_tickets VALUES",
            [(row[0], row[1], row[2], row[3], row[4]) for row in cursor.fetchall()],
        )

        cursor.close()
        pg_conn.close()


with DAG(
    "clickhouse_dwh",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    default_args=default_args,
) as dag:
    transfer_data_task = PythonOperator(
        task_id="transfer_data", python_callable=transfer_data
    )

    transfer_data_task