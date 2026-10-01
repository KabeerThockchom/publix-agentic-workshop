# Databricks notebook source
# MAGIC %md
# MAGIC # StoreSight IQ - Labor Optimization Model
# MAGIC 
# MAGIC This notebook trains a classification model to predict optimal staffing levels:
# MAGIC 1. Feature engineering from transaction and staffing patterns
# MAGIC 2. Train multiple classifiers (LightGBM, XGBoost, Random Forest)
# MAGIC 3. Compare performance and select best model
# MAGIC 4. Register in MLflow and deploy to Model Serving
# MAGIC 
# MAGIC **Task Type:** Multi-class Classification (predict staff count: 2-8 people)
# MAGIC 
# MAGIC **Models trained:**
# MAGIC - LightGBM Classifier (handles class imbalance well)
# MAGIC - XGBoost Classifier (robust multi-class performance)
# MAGIC - Random Forest Classifier (interpretable baseline)
# MAGIC 
# MAGIC **Prerequisites:** Run notebooks 01 and 02 first

# COMMAND ----------

# MAGIC %md
# MAGIC ## Install Required Packages

# COMMAND ----------

# MAGIC %pip install mlflow lightgbm xgboost scikit-learn --quiet

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Import Libraries
# MAGIC 
# MAGIC All imports must be after restartPython()

# COMMAND ----------

# Core imports
import pandas as pd
import numpy as np
import time

# PySpark
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import IntegerType

# ML Libraries
import mlflow
import mlflow.sklearn
import mlflow.lightgbm
import mlflow.xgboost
from mlflow.models import infer_signature
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
import lightgbm as lgb
import xgboost as xgb

print("✓ All libraries imported successfully")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

dbutils.widgets.text("catalog", "publix_labor_forecast")
dbutils.widgets.text("schema", "storesight_iq_publix")
dbutils.widgets.text("resource_prefix", "storesight-publix")
dbutils.widgets.text("domain_json_path", "")

CATALOG_NAME = dbutils.widgets.get("catalog")
SCHEMA_NAME = dbutils.widgets.get("schema")
PREFIX = dbutils.widgets.get("resource_prefix")
MODEL_NAME = f"{PREFIX.replace('-', '_')}_labor_optimizer"
ENDPOINT_NAME = f"{PREFIX}-labor-optimizer"

# Model parameters
TEST_SIZE = 0.2
RANDOM_STATE = 42

# Staff levels to predict (classification targets)
MIN_STAFF = 2
MAX_STAFF = 8

# COMMAND ----------

spark.sql(f"USE CATALOG {CATALOG_NAME}")
spark.sql(f"USE SCHEMA {SCHEMA_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load and Prepare Data

# COMMAND ----------

# Load transaction data for traffic patterns
transactions = spark.table("pos_transactions")

# Create hourly aggregations
hourly_data = transactions.groupBy(
    "store_id",
    F.date_format("timestamp", "yyyy-MM-dd").alias("date"),
    F.hour("timestamp").alias("hour")
).agg(
    F.count("*").alias("transactions"),
    F.sum("total").alias("revenue"),
    F.avg("total").alias("avg_ticket")
)

# Add temporal features
hourly_data = hourly_data.withColumn("date_parsed", F.to_date("date"))
hourly_data = hourly_data.withColumn("day_of_week", F.dayofweek("date_parsed"))
hourly_data = hourly_data.withColumn("is_weekend", F.when(F.col("day_of_week").isin([1, 7]), 1).otherwise(0))
hourly_data = hourly_data.withColumn("month", F.month("date_parsed"))

# Add daypart features
hourly_data = hourly_data.withColumn("is_breakfast", 
    F.when((F.col("hour") >= 6) & (F.col("hour") < 10), 1).otherwise(0))
hourly_data = hourly_data.withColumn("is_lunch", 
    F.when((F.col("hour") >= 11) & (F.col("hour") < 14), 1).otherwise(0))
hourly_data = hourly_data.withColumn("is_dinner", 
    F.when((F.col("hour") >= 17) & (F.col("hour") < 20), 1).otherwise(0))

print(f"Hourly records: {hourly_data.count():,}")
hourly_data.show(5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create Optimal Staffing Labels
# MAGIC 
# MAGIC We calculate optimal staffing based on industry rules:
# MAGIC - 1 staff per 8-10 transactions/hour
# MAGIC - Minimum 2, maximum 8 staff
# MAGIC - +1 during rush hours

# COMMAND ----------

from pyspark.sql.types import IntegerType

def calculate_optimal_staff(transactions, is_lunch, is_dinner):
    """Calculate optimal staff based on demand."""
    # Base: 1 staff per 8 transactions
    base_staff = max(2, min(8, int(transactions / 8) + 1))
    
    # Add 1 during rush hours if high volume
    if (is_lunch or is_dinner) and transactions > 25:
        base_staff = min(8, base_staff + 1)
    
    return base_staff

# Register UDF
@F.udf(IntegerType())
def optimal_staff_udf(transactions, is_lunch, is_dinner):
    return calculate_optimal_staff(transactions, is_lunch, is_dinner)

# Apply to create labels
hourly_data = hourly_data.withColumn(
    "optimal_staff",
    optimal_staff_udf(F.col("transactions"), F.col("is_lunch"), F.col("is_dinner"))
)

# Check class distribution
print("Staff Level Distribution:")
hourly_data.groupBy("optimal_staff").count().orderBy("optimal_staff").show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Feature Engineering

# COMMAND ----------

# Add lag features (previous hour, same hour yesterday)
window_hour = Window.partitionBy("store_id", "hour").orderBy("date")
window_store = Window.partitionBy("store_id").orderBy("date", "hour")

hourly_data = hourly_data.withColumn("txn_prev_hour", F.lag("transactions", 1).over(window_store))
hourly_data = hourly_data.withColumn("txn_same_hour_yesterday", F.lag("transactions", 24).over(window_store))
hourly_data = hourly_data.withColumn("txn_same_hour_last_week", F.lag("transactions", 168).over(window_store))

# Rolling average for the hour
hourly_data = hourly_data.withColumn(
    "txn_hourly_avg_7d", 
    F.avg("transactions").over(Window.partitionBy("store_id", "hour").orderBy("date").rowsBetween(-7, -1))
)

# Select features for training
feature_columns = [
    # Temporal
    "hour", "day_of_week", "is_weekend", "month",
    # Daypart indicators
    "is_breakfast", "is_lunch", "is_dinner",
    # Traffic metrics
    "transactions", "revenue", "avg_ticket",
    # Lag features
    "txn_prev_hour", "txn_same_hour_yesterday", "txn_same_hour_last_week",
    "txn_hourly_avg_7d",
    # Store
    "store_id",
    # Target
    "optimal_staff"
]

# Prepare final dataset
training_df = hourly_data.select(feature_columns).dropna()
print(f"Training samples: {training_df.count():,}")

# Convert to Pandas
train_pdf = training_df.toPandas()
train_pdf = train_pdf.replace([np.inf, -np.inf], np.nan).fillna(0)

print(f"\nDataset shape: {train_pdf.shape}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Train/Test Split

# COMMAND ----------

from sklearn.model_selection import train_test_split

# Separate features and target
X = train_pdf.drop(columns=["optimal_staff"])
y_original = train_pdf["optimal_staff"]

# Shift labels to 0-indexed for XGBoost compatibility
# Staff levels 2-8 become 0-6
y = y_original - MIN_STAFF

# Split data with stratification (maintains class balance)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=TEST_SIZE, 
    random_state=RANDOM_STATE,
    stratify=y  # Maintain class distribution
)

print(f"Training set: {len(X_train):,} samples")
print(f"Test set: {len(X_test):,} samples")
print(f"\nClass distribution in test set (0-indexed, add {MIN_STAFF} for actual staff):")
print(y_test.value_counts().sort_index())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Train Classification Models

# COMMAND ----------

# Set experiment
experiment_name = f"/Users/{spark.sql('SELECT current_user()').first()[0]}/{MODEL_NAME}"
mlflow.set_experiment(experiment_name)

def evaluate_classifier(model, X_test, y_test, model_name):
    """Evaluate classification model."""
    y_pred = model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    f1_weighted = f1_score(y_test, y_pred, average='weighted')
    f1_macro = f1_score(y_test, y_pred, average='macro')
    
    # Calculate "within 1" accuracy (prediction within 1 of actual)
    within_1 = np.mean(np.abs(y_test - y_pred) <= 1)
    
    print(f"\n{model_name} Results:")
    print(f"  Accuracy:       {accuracy:.4f}")
    print(f"  F1 (weighted):  {f1_weighted:.4f}")
    print(f"  F1 (macro):     {f1_macro:.4f}")
    print(f"  Within ±1:      {within_1:.4f}")
    
    return {
        "accuracy": accuracy,
        "f1_weighted": f1_weighted,
        "f1_macro": f1_macro,
        "within_1_accuracy": within_1
    }

results = {}

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model 1: LightGBM Classifier
# MAGIC 
# MAGIC Best for: Fast training, handles imbalanced classes, gradient boosting

# COMMAND ----------

print("Training LightGBM Classifier...")
start_time = time.time()

with mlflow.start_run(run_name="LightGBM_Labor_Optimizer") as run:
    # Get unique classes for num_class parameter
    num_classes = len(y.unique())
    
    lgb_params = {
        "objective": "multiclass",
        "num_class": num_classes,
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "max_depth": 6,
        "learning_rate": 0.05,
        "n_estimators": 300,
        "min_child_samples": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "class_weight": "balanced",  # Handle class imbalance
        "random_state": RANDOM_STATE,
        "verbose": -1
    }
    
    lgb_model = lgb.LGBMClassifier(**lgb_params)
    lgb_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
    )
    
    train_time = time.time() - start_time
    metrics = evaluate_classifier(lgb_model, X_test, y_test, "LightGBM")
    metrics["train_time"] = train_time
    results["LightGBM"] = {"model": lgb_model, "run_id": run.info.run_id, "metrics": metrics}
    
    mlflow.log_params(lgb_params)
    mlflow.log_metrics(metrics)
    
    # Create signature for Unity Catalog (required)
    predictions = lgb_model.predict(X_train[:100])
    signature = infer_signature(X_train[:100], predictions)
    mlflow.lightgbm.log_model(lgb_model, "model", signature=signature)

print(f"\nTraining time: {train_time:.1f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model 2: XGBoost Classifier
# MAGIC 
# MAGIC Best for: Robust multi-class, regularization, industry standard

# COMMAND ----------

print("Training XGBoost Classifier...")
start_time = time.time()

with mlflow.start_run(run_name="XGBoost_Labor_Optimizer") as run:
    xgb_params = {
        "objective": "multi:softmax",
        "num_class": num_classes,
        "max_depth": 6,
        "learning_rate": 0.05,
        "n_estimators": 300,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
        "verbosity": 0
    }
    
    xgb_model = xgb.XGBClassifier(**xgb_params)
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    train_time = time.time() - start_time
    metrics = evaluate_classifier(xgb_model, X_test, y_test, "XGBoost")
    metrics["train_time"] = train_time
    results["XGBoost"] = {"model": xgb_model, "run_id": run.info.run_id, "metrics": metrics}
    
    mlflow.log_params(xgb_params)
    mlflow.log_metrics(metrics)
    
    # Create signature for Unity Catalog (required)
    predictions = xgb_model.predict(X_train[:100])
    signature = infer_signature(X_train[:100], predictions)
    mlflow.xgboost.log_model(xgb_model, "model", signature=signature)

print(f"\nTraining time: {train_time:.1f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model 3: Random Forest Classifier
# MAGIC 
# MAGIC Best for: Robust baseline, interpretable, less overfitting

# COMMAND ----------

print("Training Random Forest Classifier...")
start_time = time.time()

with mlflow.start_run(run_name="RandomForest_Labor_Optimizer") as run:
    rf_params = {
        "n_estimators": 200,
        "max_depth": 12,
        "min_samples_split": 10,
        "min_samples_leaf": 5,
        "max_features": "sqrt",
        "class_weight": "balanced",
        "random_state": RANDOM_STATE,
        "n_jobs": -1
    }
    
    rf_model = RandomForestClassifier(**rf_params)
    rf_model.fit(X_train, y_train)
    
    train_time = time.time() - start_time
    metrics = evaluate_classifier(rf_model, X_test, y_test, "Random Forest")
    metrics["train_time"] = train_time
    results["RandomForest"] = {"model": rf_model, "run_id": run.info.run_id, "metrics": metrics}
    
    mlflow.log_params(rf_params)
    mlflow.log_metrics(metrics)
    
    # Create signature for Unity Catalog (required)
    predictions = rf_model.predict(X_train[:100])
    signature = infer_signature(X_train[:100], predictions)
    # serialization_format="cloudpickle": MLflow 3.14 defaults sklearn logging to
    # skops, which rejects tree-based estimators. cloudpickle keeps the classic,
    # load-compatible serialization.
    mlflow.sklearn.log_model(rf_model, "model", signature=signature, serialization_format="cloudpickle")

print(f"\nTraining time: {train_time:.1f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Model Comparison

# COMMAND ----------

comparison_data = []
for name, data in results.items():
    m = data["metrics"]
    comparison_data.append({
        "Model": name,
        "Accuracy": f"{m['accuracy']:.4f}",
        "F1 Weighted": f"{m['f1_weighted']:.4f}",
        "F1 Macro": f"{m['f1_macro']:.4f}",
        "Within ±1": f"{m['within_1_accuracy']:.4f}",
        "Time": f"{m['train_time']:.1f}s"
    })

comparison_df = pd.DataFrame(comparison_data)
print("\n" + "="*80)
print("MODEL COMPARISON - Labor Optimization (Classification)")
print("="*80)
print(comparison_df.to_string(index=False))
print("="*80)

# Select best model based on F1 weighted score
best_model_name = max(results, key=lambda x: results[x]["metrics"]["f1_weighted"])
best_model_data = results[best_model_name]

print(f"\n✓ Best Model: {best_model_name}")
print(f"  F1 Score: {best_model_data['metrics']['f1_weighted']:.4f}")
print(f"  Within ±1 Accuracy: {best_model_data['metrics']['within_1_accuracy']:.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Confusion Matrix Analysis

# COMMAND ----------

import matplotlib.pyplot as plt

# Get predictions from best model
y_pred = best_model_data["model"].predict(X_test)

# Print classification report (labels are 0-indexed; add MIN_STAFF for actual staff count)
print("\nClassification Report (Best Model):")
print(f"Note: Class labels are 0-indexed. Add {MIN_STAFF} for actual staff count.")
print(classification_report(y_test, y_pred, digits=3))

# Confusion matrix
cm = confusion_matrix(y_test, y_pred)
print("\nConfusion Matrix (rows/cols are 0-indexed staff levels):")
print(cm)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Register and Deploy Best Model

# COMMAND ----------

# Register model
model_uri = f"runs:/{best_model_data['run_id']}/model"
full_model_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}"

registered_model = mlflow.register_model(model_uri=model_uri, name=full_model_name)

print(f"✓ Model registered: {registered_model.name} v{registered_model.version}")

# Set production alias
client = mlflow.tracking.MlflowClient()
client.set_registered_model_alias(name=full_model_name, alias="production", version=registered_model.version)

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput

w = WorkspaceClient()

try:
    w.serving_endpoints.get(ENDPOINT_NAME)
    print(f"Updating endpoint '{ENDPOINT_NAME}'...")
    w.serving_endpoints.update_config_and_wait(
        name=ENDPOINT_NAME,
        served_entities=[ServedEntityInput(
            entity_name=full_model_name,
            entity_version=str(registered_model.version),
            workload_size="Small",
            scale_to_zero_enabled=True
        )]
    )
except:
    print(f"Creating endpoint '{ENDPOINT_NAME}'...")
    w.serving_endpoints.create_and_wait(
        name=ENDPOINT_NAME,
        config=EndpointCoreConfigInput(name=ENDPOINT_NAME, served_entities=[ServedEntityInput(
            entity_name=full_model_name,
            entity_version=str(registered_model.version),
            workload_size="Small",
            scale_to_zero_enabled=True
        )])
    )

print(f"✓ Endpoint '{ENDPOINT_NAME}' is ready!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("="*70)
print("LABOR OPTIMIZATION MODEL - TRAINING COMPLETE")
print("="*70)
print(f"""
Model Details:
  • Task: Multi-class Classification (Staff Level {MIN_STAFF}-{MAX_STAFF})
  • Labels: 0-indexed internally (prediction + {MIN_STAFF} = actual staff)
  • Best Algorithm: {best_model_name}
  • F1 Score (weighted): {best_model_data['metrics']['f1_weighted']:.4f}
  • Within ±1 Accuracy: {best_model_data['metrics']['within_1_accuracy']:.4f}

Deployment:
  • Model: {full_model_name}
  • Version: {registered_model.version}
  • Endpoint: {ENDPOINT_NAME}

Features Used ({len(X_train.columns)}):
  • Temporal: hour, day_of_week, is_weekend, month
  • Daypart: is_breakfast, is_lunch, is_dinner
  • Traffic: transactions, revenue, avg_ticket
  • Lag: previous hour, same hour yesterday/last week

Next: Run notebook 04_train_inventory_prediction_model.py
""")
print("="*70)
