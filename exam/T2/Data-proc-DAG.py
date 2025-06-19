import uuid
import datetime
from airflow import DAG
from airflow.utils.trigger_rule import TriggerRule
from airflow.providers.yandex.operators.yandexcloud_dataproc import (
    DataprocCreateClusterOperator,
    DataprocCreatePysparkJobOperator,
    DataprocDeleteClusterOperator,
)

# Данные инфраструктуры
YC_DP_AZ = 'ru-central1-a'
YC_DP_SSH_PUBLIC_KEY = 'ssh-rsa bBzQ+PqXVa0KyLSDTeSan+N+2HZkRY3rt+4/8/2GtgQ Иван@DESKTOP-53I2BCO'
YC_DP_SUBNET_ID = 'e2l0d3q9vj7r5h6g8f2k'
YC_DP_SA_ID = 'aje12345qwerty67890'
YC_DP_METASTORE_URI = '192.168.1.100'
YC_BUCKET = 'tumkabacket'

# Настройки DAG
with DAG(
        'DATA_INGEST',
        schedule_interval='@hourly',
        tags=['data-processing-and-airflow'],
        start_date=datetime.datetime.now(),
        max_active_runs=1,
        catchup=False
) as ingest_dag:
    # 1 этап
    create_spark_cluster = DataprocCreateClusterOperator(
        task_id='dp-cluster-create-task',
        cluster_name=f'tmp-dp-{uuid.uuid4()}',
        cluster_description='Временный кластер для выполнения PySpark-задания под оркестрацией Managed Service for Apache Airflow™',
        ssh_public_keys=YC_DP_SSH_PUBLIC_KEY,
        service_account_id=YC_DP_SA_ID,
        subnet_id=YC_DP_SUBNET_ID,
        s3_bucket=YC_BUCKET,
        zone=YC_DP_AZ,
        cluster_image_version='2.1',
        masternode_resource_preset='s2.small', 
        masternode_disk_type='network-hdd',
        masternode_disk_size=32, 
        computenode_resource_preset='s2.small',  
        computenode_disk_type='network-hdd',
        computenode_disk_size=32,  
        computenode_count=1, 
        computenode_max_hosts_count=3, 
        services=['YARN', 'SPARK'],
        datanode_count=0,
        properties={
            'spark:spark.hive.metastore.uris': f'thrift://{YC_DP_METASTORE_URI}:9083',
        },
    )

    # 2 этап
    poke_spark_processing = DataprocCreatePysparkJobOperator(
        task_id='dp-cluster-pyspark-task',
        main_python_file_uri=f's3a://{YC_BUCKET}/scripts/clean-data.py',
    )

    # 3 этап
    delete_spark_cluster = DataprocDeleteClusterOperator(
        task_id='dp-cluster-delete-task',
        trigger_rule=TriggerRule.ALL_DONE,
    )

    # Формирование DAG
    create_spark_cluster >> poke_spark_processing >> delete_spark_cluster
