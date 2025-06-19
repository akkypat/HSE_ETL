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
    # df = df.na.drop()
            
    print("Пример данных после преобразования:")
    df.show(5)
            
    print(f"Запись в Parquet: {target_path}")
    df.write.mode("overwrite").parquet(target_path)
            
    print("✅ Данные успешно сохранены в Parquet.")

except AnalysisException as ae:
    print("❌ Ошибка анализа:", ae)
except Exception as e:
    print("❌ Общая ошибка:", e)
	
spark.stop()