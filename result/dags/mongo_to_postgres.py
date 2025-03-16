from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import json
from lib import default_args, mongo_client, pg_conn
import logging


def migrate_user_sessions() -> None:
    user_sessions = mongo_client["raw_data"]["user_sessions"]
    support_tickets = mongo_client["raw_data"]["support_tickets"]

    """
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id INT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            pages_visited JSONB,
            device JSONB,
            actions JSONB
        )
    """

    """
        CREATE TABLE IF NOT EXISTS replicated_data.support_tickets (
                ticket_id TEXT PRIMARY KEY,
                user_id INT,
                status TEXT,
                issue_type TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
    """

    last_hour = datetime.now() - timedelta(hours=1)
    sessions = user_sessions.find({"start_time": {"$gte": last_hour}})
    tickets = support_tickets.find({"updated_at": {"$gte": last_hour}})

    with pg_conn.cursor() as cursor:
        for session in sessions:
            cursor.execute(
                query="""
                INSERT INTO replicated_data.user_sessions 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO NOTHING
            """,
                vars=(
                    session["session_id"],
                    session["user_id"],
                    session["start_time"],
                    session["end_time"],
                    json.dumps(session["pages_visited"]),
                    json.dumps(session["device"]),
                    json.dumps(session["actions"]),
                ),
            )

        for ticket in tickets:
            cursor.execute(
                query="""
                INSERT INTO replicated_data.support_tickets 
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticket_id) DO NOTHING
            """,
                vars=(
                    ticket["ticket_id"],
                    ticket["user_id"],
                    ticket["status"],
                    ticket["issue_type"],
                    ticket["created_at"],
                    ticket["updated_at"],
                ),
            )
            
        pg_conn.commit()
        pg_conn.close()


with DAG(
    "mongo_to_postgres",
    default_args=default_args,
    schedule_interval="@hourly",
    start_date=datetime(2024, 1, 1),
) as dag:
    migrate_task = PythonOperator(
        task_id="migrate_user_sessions", python_callable=migrate_user_sessions
    )

