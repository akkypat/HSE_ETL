from datetime import datetime
import pymongo
import psycopg2
from clickhouse_driver import Client

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 3, 1),
}


mongo_client = pymongo.MongoClient(
        host="localhost",
        port=27017,
        username="root",
        password="example",
    )

pg_conn = psycopg2.connect(
        dbname='airflow',
        user='airflow',
        password='airflow',
        host='postgres'
    )

ch_client = Client(host='localhost', user='admin', password='secret',)