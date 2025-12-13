from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler, StringIndexer
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml import Pipeline

def main():
    spark = SparkSession.builder \
        .appName("Iris Classification from CSV") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()

    print("Loading csv")
    df = spark.read.csv("s3a://hse-storage-spark/iris.csv", header=True, inferSchema=True)
    print("Completed")

    feature_cols = [col for col in df.columns if col != "species"]
    print(f"Features: {feature_cols}")

    # Преобразование категориальной переменной в числовую
    indexer = StringIndexer(
        inputCol="species",
        outputCol="label",
        handleInvalid="keep")

    # Объединение признаков в вектор
    assembler = VectorAssembler(
        inputCols=feature_cols,
        outputCol="features",
        handleInvalid="skip")

    # Разделение на train/test
    train_data, test_data = df.randomSplit([0.8, 0.2], seed=42)

    print(f"\nTrain set: {train_data.count()}")
    print(f"Test set: {test_data.count()}")

    print("Processing Random Forest")
    rf = RandomForestClassifier(
        featuresCol="features",
        labelCol="label",
        numTrees=100,
        maxDepth=5,
        seed=42)

    pipeline_rf = Pipeline(stages=[indexer, assembler, rf])

    model_rf = pipeline_rf.fit(train_data)
    print("Completed")

    predictions_rf = model_rf.transform(test_data)

    evaluator_acc = MulticlassClassificationEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="accuracy")

    evaluator_f1 = MulticlassClassificationEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="f1")

    evaluator_precision = MulticlassClassificationEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="weightedPrecision")

    evaluator_recall = MulticlassClassificationEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="weightedRecall")

    accuracy_rf = evaluator_acc.evaluate(predictions_rf)
    f1_rf = evaluator_f1.evaluate(predictions_rf)
    precision_rf = evaluator_precision.evaluate(predictions_rf)
    recall_rf = evaluator_recall.evaluate(predictions_rf)

    print(f"\nAccuracy:  {accuracy_rf:.4f}")
    print(f"F1 Score:  {f1_rf:.4f}")
    print(f"Precision: {precision_rf:.4f}")
    print(f"Recall:    {recall_rf:.4f}")

    print("\nSaving data")
    model_rf.write().overwrite().save("s3a://hse-storage-spark/iris_random_forest_model")
    print(f"Completed")

    spark.stop()

if __name__ == '__main__':
    main()
