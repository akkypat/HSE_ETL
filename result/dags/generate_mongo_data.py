from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import random
from lib import default_args, mongo_client
import uuid


COUNT_ROWS_TO_GENERATE = 1000


def generate_user_session() -> dict:
    return {
        "session_id": str(random.randint(10**3, 10**6)),
        "user_id": random.randint(10**1, 10**3),
        "start_time": datetime.now(),
        "end_time": datetime.now() + timedelta(minutes=random.randint(1, 60)),
        "pages_visited": ["/home", "/product"],
        "device": {"type": "mobile", "os": "Android"},
        "actions": ["click", "scroll"],
    }


def generate_support_ticket() -> dict:
    return {
        "ticket_id": str(object=uuid.uuid4()),
        "user_id": random.randint(10**1, 10**3),
        "status": random.choice(["open", "closed", "pending"]),
        "issue_type": random.choice(["technical", "billing", "general"]),
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


def generate_data() -> None:
    collection = mongo_client["raw_data"]["user_sessions"]
    support_tickets = mongo_client["raw_data"]["support_tickets"]

    documents: list[dict] = [
        generate_user_session() for _ in range(COUNT_ROWS_TO_GENERATE)
    ]

    tickets: list[dict] = [
        generate_support_ticket() for _ in range(COUNT_ROWS_TO_GENERATE)
    ]

    collection.insert_many(documents)
    support_tickets.insert_many(tickets)


dag = DAG(
    "generate_mongo_data",
    default_args=default_args,
    schedule_interval="*/10 * * * *",
    catchup=False,
)

generate_task = PythonOperator(
    task_id="generate_mongo_data", python_callable=generate_data, dag=dag
)

