
# Итоговому заданию за 4 модуль

## Структура:
1) **Данные:** `transactions_v2.csv`
2) **ETL-пайплай:** Airflow + Dataproc
3) **Форматы:** CSV + Parquet

### Задание 1.

- Создаем таблицу в YDB через SQL скрипт  
    ### SQL скрипт
    ```
    CREATE TABLE transactions_v2 (
          msno Utf8,
          payment_method_id Int32,
          payment_plan_days Int32,
          plan_list_price Int32,
          actual_amount_paid Int32,
          is_auto_renew Int8,
          transaction_date Utf8,
          membership_expire_date Utf8,
          is_cancel Int8,
          PRIMARY KEY (msno)
      );
    ```
- В созданную таблицу с помощью CLI загружаем датасет "transaction_v2"
    ### bash-скрипт для загрузки данных
    ```
    ydb  `
    --endpoint grpcs://ydb.serverless.yandexcloud.net:2135 `
    --database /ru-central1/b1g9tm1cvjc9r6hl0g83/etn4ciikjn2811hfpjo9 `
    --sa-key-file authorized_key.json `
    import file csv `
    --path transactions_v2 `
    --delimiter "," `
    --skip-rows 1 `
    --null-value "" `
    --verbose `
    transactions_v2.csv
    ```
- Создаем трансферс источником в YDB и приемником в Object Storage
  ```
  transactions_v2.parquet
  ``` 

### Задание 2.

- Создаем инфраструктуру Managed service for Apache Airflow
- Создаем DAG **DATA_INGEST**, с помощью которого cоздаем Data Proc кластер и запускаем на кластере PySpark-задание.
    - После завершения работы задания удаляет кластер.
	 ### Data-proc-DAG.py
	 ```import uuid
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
		create_spark_cluster >> poke_spark_processing >> delete_spark_cluster```

	Далее выполняем следующие действия:
	- Приведение типов всех полей (`Integer`, `Boolean`, `Date`, `String`)
	- Удаление пустых строк
	- Преобразование transaction_date и membership_expire_date в DateType
	- Результат сохраняется в формате Parquet:
		### clean-data.py
		python
		from pyspark.sql import SparkSession
		from pyspark.sql.functions import col, to_date
		from pyspark.sql.types import IntegerType, StringType, BooleanType
		from pyspark.sql.utils import AnalysisException
			
		# spark
		spark = SparkSession.builder.appName("Parquet ETL with Logging to S3").getOrCreate()
			
		source_path = "/transactions_v2.csv"
		target_path = "/transactions_v2_clean.parquet"
		
		try:
			print(f"Чтение данных из: {source_path}")
			df = spark.read.option("header", "true").option("inferSchema", "true").csv(source_path)
		
			print("Схема исходных данных:")
			df.printSchema()
		
			# YYYYMMDD
			df = df.withColumn("actual_amount_paid", col("actual_amount_paid").cast(IntegerType())) \
				.withColumn("is_auto_renew", col("is_auto_renew").cast(BooleanType())) \
				.withColumn("is_cancel", col("is_cancel").cast(BooleanType())) \
				.withColumn("membership_expire_date", to_date(col("membership_expire_date").cast("string"), "yyyyMMdd")) \
				.withColumn("msno", col("msno").cast(StringType())) \
				.withColumn("payment_method_id", col("payment_method_id").cast(IntegerType())) \
				.withColumn("payment_plan_days", col("payment_plan_days").cast(IntegerType())) \
				.withColumn("plan_list_price", col("plan_list_price").cast(IntegerType())) \
				.withColumn("transaction_date", to_date(col("transaction_date").cast("string"),  "yyyyMMdd"))
		
			print("Схема преобразованных данных:")
			df.printSchema()
		
			# Удаление пустых строк
			df = df.na.drop()
		
			print("Пример данных после преобразования:")
			df.show(10)
		
			print(f"Запись в Parquet: {target_path}")
			df.write.mode("overwrite").parquet(target_path)
		
			print("✅ Данные успешно сохранены в Parquet.")

		except AnalysisException as ae:
			print("❌ Ошибка анализа:", ae)
		except Exception as e:
			print("❌ Общая ошибка:", e)
		
		spark.stop()
	```