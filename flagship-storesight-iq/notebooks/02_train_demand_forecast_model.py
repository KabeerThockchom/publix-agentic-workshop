# Databricks notebook source
# MAGIC %md
# MAGIC # StoreSight IQ - Demand Forecasting Model
# MAGIC 
# MAGIC This notebook trains and deploys a demand forecasting model using explicit ML algorithms:
# MAGIC 1. Feature engineering from historical transactions
# MAGIC 2. Train multiple models (LightGBM, XGBoost, Random Forest)
# MAGIC 3. Compare performance and select best model
# MAGIC 4. Register in MLflow and deploy to Model Serving
# MAGIC 
# MAGIC **Prerequisites:** Run notebook 01_generate_data_and_streaming.py first
# MAGIC 
# MAGIC **Models trained:**
# MAGIC - LightGBM Regressor (gradient boosting - fast & accurate)
# MAGIC - XGBoost Regressor (industry standard for tabular data)
# MAGIC - Random Forest Regressor (robust baseline)

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

# ML Libraries
import mlflow
import mlflow.sklearn
import mlflow.lightgbm
import mlflow.xgboost
from mlflow.models import infer_signature
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import lightgbm as lgb
import xgboost as xgb

print("✓ All libraries imported successfully")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

dbutils.widgets.text("catalog", "publix_technology")
dbutils.widgets.text("schema", "storesight_iq_publix")
dbutils.widgets.text("resource_prefix", "storesight-publix")
dbutils.widgets.text("domain_json_path", "")

CATALOG_NAME = dbutils.widgets.get("catalog")
SCHEMA_NAME = dbutils.widgets.get("schema")
PREFIX = dbutils.widgets.get("resource_prefix")
MODEL_NAME = f"{PREFIX.replace('-', '_')}_demand_forecast"
ENDPOINT_NAME = f"{PREFIX}-demand-forecast"

# Model training parameters
TEST_SIZE = 0.2
RANDOM_STATE = 42

# COMMAND ----------

spark.sql(f"USE CATALOG {CATALOG_NAME}")
spark.sql(f"USE SCHEMA {SCHEMA_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load and Explore Data

# COMMAND ----------

# Load transaction data
transactions = spark.table("pos_transactions")
print(f"Total transactions: {transactions.count():,}")

# Show date range
transactions.select(
    F.min("timestamp").alias("start_date"),
    F.max("timestamp").alias("end_date"),
    F.countDistinct("store_id").alias("num_stores")
).show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Feature Engineering
# MAGIC 
# MAGIC Create features commonly used in demand forecasting:
# MAGIC - **Temporal features**: day of week, month, is_weekend, is_holiday
# MAGIC - **Lag features**: previous day, previous week
# MAGIC - **Rolling features**: 7-day and 14-day moving averages
# MAGIC - **Store features**: store-level aggregates

# COMMAND ----------

# Create daily aggregations with features
daily_data = transactions.groupBy(
    "store_id",
    F.date_format("timestamp", "yyyy-MM-dd").alias("date")
).agg(
    F.count("*").alias("transaction_count"),
    F.sum("total").alias("revenue"),
    F.avg("total").alias("avg_ticket"),
    F.countDistinct("channel").alias("unique_channels")
)

# Parse date and add temporal features
daily_data = daily_data.withColumn("date_parsed", F.to_date("date"))
daily_data = daily_data.withColumn("day_of_week", F.dayofweek("date_parsed"))
daily_data = daily_data.withColumn("day_of_month", F.dayofmonth("date_parsed"))
daily_data = daily_data.withColumn("month", F.month("date_parsed"))
daily_data = daily_data.withColumn("week_of_year", F.weekofyear("date_parsed"))
daily_data = daily_data.withColumn("is_weekend", F.when(F.col("day_of_week").isin([1, 7]), 1).otherwise(0))

# Quarter feature
daily_data = daily_data.withColumn("quarter", F.quarter("date_parsed"))

# Is month start/end
daily_data = daily_data.withColumn("is_month_start", F.when(F.col("day_of_month") <= 3, 1).otherwise(0))
daily_data = daily_data.withColumn("is_month_end", F.when(F.col("day_of_month") >= 28, 1).otherwise(0))

print(f"Daily records: {daily_data.count():,}")
daily_data.show(5)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Add Lag Features

# COMMAND ----------

# Define window for lag calculations (partition by store, order by date)
window_spec = Window.partitionBy("store_id").orderBy("date")

# Lag features - previous days' values
daily_data = daily_data.withColumn("txn_lag_1", F.lag("transaction_count", 1).over(window_spec))
daily_data = daily_data.withColumn("txn_lag_2", F.lag("transaction_count", 2).over(window_spec))
daily_data = daily_data.withColumn("txn_lag_7", F.lag("transaction_count", 7).over(window_spec))
daily_data = daily_data.withColumn("txn_lag_14", F.lag("transaction_count", 14).over(window_spec))

# Revenue lag features
daily_data = daily_data.withColumn("revenue_lag_1", F.lag("revenue", 1).over(window_spec))
daily_data = daily_data.withColumn("revenue_lag_7", F.lag("revenue", 7).over(window_spec))

# Rolling window features (7-day and 14-day moving averages)
window_7d = Window.partitionBy("store_id").orderBy("date").rowsBetween(-7, -1)
window_14d = Window.partitionBy("store_id").orderBy("date").rowsBetween(-14, -1)

daily_data = daily_data.withColumn("txn_rolling_7d_avg", F.avg("transaction_count").over(window_7d))
daily_data = daily_data.withColumn("txn_rolling_7d_std", F.stddev("transaction_count").over(window_7d))
daily_data = daily_data.withColumn("txn_rolling_14d_avg", F.avg("transaction_count").over(window_14d))
daily_data = daily_data.withColumn("revenue_rolling_7d_avg", F.avg("revenue").over(window_7d))

# Week-over-week change
daily_data = daily_data.withColumn(
    "txn_wow_change", 
    (F.col("txn_lag_1") - F.col("txn_lag_7")) / F.col("txn_lag_7")
)

print("Features added:")
daily_data.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Prepare Final Training Dataset

# COMMAND ----------

# Select features for training
feature_columns = [
    # Temporal
    "day_of_week", "day_of_month", "month", "week_of_year", "quarter",
    "is_weekend", "is_month_start", "is_month_end",
    # Lag features
    "txn_lag_1", "txn_lag_2", "txn_lag_7", "txn_lag_14",
    "revenue_lag_1", "revenue_lag_7",
    # Rolling features
    "txn_rolling_7d_avg", "txn_rolling_7d_std", "txn_rolling_14d_avg",
    "revenue_rolling_7d_avg",
    # WoW change
    "txn_wow_change",
    # Store
    "store_id",
    # Target
    "transaction_count"
]

# Filter to only include rows with complete features (drop rows with nulls from lag)
training_df = daily_data.select(feature_columns).dropna()

print(f"Training samples after dropping nulls: {training_df.count():,}")

# Convert to Pandas for sklearn
train_pdf = training_df.toPandas()

# Replace infinities with NaN and then fill with 0
train_pdf = train_pdf.replace([np.inf, -np.inf], np.nan).fillna(0)

print(f"\nDataset shape: {train_pdf.shape}")
print(f"\nFeature statistics:")
print(train_pdf.describe())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Train/Test Split

# COMMAND ----------

from sklearn.model_selection import train_test_split

# Separate features and target
X = train_pdf.drop(columns=["transaction_count"])
y = train_pdf["transaction_count"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=TEST_SIZE, 
    random_state=RANDOM_STATE
)

print(f"Training set: {len(X_train):,} samples")
print(f"Test set: {len(X_test):,} samples")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Train Models
# MAGIC 
# MAGIC We'll train three popular models for demand forecasting:

# COMMAND ----------

# Set experiment
experiment_name = f"/Users/{spark.sql('SELECT current_user()').first()[0]}/{MODEL_NAME}"
mlflow.set_experiment(experiment_name)

def evaluate_model(model, X_test, y_test, model_name):
    """Evaluate model and return metrics."""
    y_pred = model.predict(X_test)
    
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    mape = np.mean(np.abs((y_test - y_pred) / np.maximum(y_test, 1))) * 100
    
    print(f"\n{model_name} Results:")
    print(f"  RMSE: {rmse:.2f}")
    print(f"  MAE:  {mae:.2f}")
    print(f"  R²:   {r2:.4f}")
    print(f"  MAPE: {mape:.2f}%")
    
    return {"rmse": rmse, "mae": mae, "r2": r2, "mape": mape}

# Store results for comparison
results = {}

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model 1: LightGBM (Gradient Boosting)
# MAGIC 
# MAGIC LightGBM is excellent for demand forecasting due to:
# MAGIC - Fast training on large datasets
# MAGIC - Handles categorical features natively
# MAGIC - Robust to outliers

# COMMAND ----------

print("Training LightGBM...")
start_time = time.time()

with mlflow.start_run(run_name="LightGBM_Demand_Forecast") as run:
    # LightGBM parameters optimized for demand forecasting
    lgb_params = {
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 63,
        "max_depth": 8,
        "learning_rate": 0.05,
        "n_estimators": 500,
        "min_child_samples": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "random_state": RANDOM_STATE,
        "verbose": -1
    }
    
    # Train model
    lgb_model = lgb.LGBMRegressor(**lgb_params)
    lgb_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
    )
    
    train_time = time.time() - start_time
    
    # Evaluate
    metrics = evaluate_model(lgb_model, X_test, y_test, "LightGBM")
    metrics["train_time"] = train_time
    results["LightGBM"] = {"model": lgb_model, "run_id": run.info.run_id, "metrics": metrics}
    
    # Log to MLflow
    mlflow.log_params(lgb_params)
    mlflow.log_metrics(metrics)
    
    # Create signature for Unity Catalog (required)
    predictions = lgb_model.predict(X_train[:100])
    signature = infer_signature(X_train[:100], predictions)
    mlflow.lightgbm.log_model(lgb_model, "model", signature=signature)
    
    # Log feature importance
    importance_df = pd.DataFrame({
        "feature": X_train.columns,
        "importance": lgb_model.feature_importances_
    }).sort_values("importance", ascending=False)
    
    print(f"\nTop 10 Features:")
    print(importance_df.head(10).to_string(index=False))

print(f"\nTraining time: {train_time:.1f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model 2: XGBoost (Extreme Gradient Boosting)
# MAGIC 
# MAGIC XGBoost is the industry standard for:
# MAGIC - Competition-winning performance
# MAGIC - Built-in regularization
# MAGIC - Parallel processing

# COMMAND ----------

print("Training XGBoost...")
start_time = time.time()

with mlflow.start_run(run_name="XGBoost_Demand_Forecast") as run:
    # XGBoost parameters
    xgb_params = {
        "objective": "reg:squarederror",
        "max_depth": 8,
        "learning_rate": 0.05,
        "n_estimators": 500,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
        "verbosity": 0
    }
    
    # Train model
    xgb_model = xgb.XGBRegressor(**xgb_params)
    xgb_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )
    
    train_time = time.time() - start_time
    
    # Evaluate
    metrics = evaluate_model(xgb_model, X_test, y_test, "XGBoost")
    metrics["train_time"] = train_time
    results["XGBoost"] = {"model": xgb_model, "run_id": run.info.run_id, "metrics": metrics}
    
    # Log to MLflow
    mlflow.log_params(xgb_params)
    mlflow.log_metrics(metrics)
    
    # Create signature for Unity Catalog (required)
    predictions = xgb_model.predict(X_train[:100])
    signature = infer_signature(X_train[:100], predictions)
    mlflow.xgboost.log_model(xgb_model, "model", signature=signature)

print(f"\nTraining time: {train_time:.1f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model 3: Random Forest (Ensemble of Decision Trees)
# MAGIC 
# MAGIC Random Forest provides:
# MAGIC - Robust baseline performance
# MAGIC - Less prone to overfitting
# MAGIC - Interpretable feature importance

# COMMAND ----------

print("Training Random Forest...")
start_time = time.time()

with mlflow.start_run(run_name="RandomForest_Demand_Forecast") as run:
    # Random Forest parameters
    rf_params = {
        "n_estimators": 200,
        "max_depth": 15,
        "min_samples_split": 10,
        "min_samples_leaf": 5,
        "max_features": "sqrt",
        "random_state": RANDOM_STATE,
        "n_jobs": -1
    }
    
    # Train model
    rf_model = RandomForestRegressor(**rf_params)
    rf_model.fit(X_train, y_train)
    
    train_time = time.time() - start_time
    
    # Evaluate
    metrics = evaluate_model(rf_model, X_test, y_test, "Random Forest")
    metrics["train_time"] = train_time
    results["RandomForest"] = {"model": rf_model, "run_id": run.info.run_id, "metrics": metrics}
    
    # Log to MLflow
    mlflow.log_params(rf_params)
    mlflow.log_metrics(metrics)
    
    # Create signature for Unity Catalog (required)
    predictions = rf_model.predict(X_train[:100])
    signature = infer_signature(X_train[:100], predictions)
    # serialization_format="cloudpickle": MLflow 3.14 defaults sklearn logging to
    # skops, which rejects tree-based estimators (RandomForest/GradientBoosting).
    # cloudpickle keeps the classic, load-compatible serialization.
    mlflow.sklearn.log_model(rf_model, "model", signature=signature, serialization_format="cloudpickle")

print(f"\nTraining time: {train_time:.1f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Model Comparison

# COMMAND ----------

# Create comparison table
comparison_data = []
for name, data in results.items():
    m = data["metrics"]
    comparison_data.append({
        "Model": name,
        "RMSE": f"{m['rmse']:.2f}",
        "MAE": f"{m['mae']:.2f}",
        "R²": f"{m['r2']:.4f}",
        "MAPE": f"{m['mape']:.2f}%",
        "Train Time": f"{m['train_time']:.1f}s"
    })

comparison_df = pd.DataFrame(comparison_data)
print("\n" + "="*70)
print("MODEL COMPARISON")
print("="*70)
print(comparison_df.to_string(index=False))
print("="*70)

# Select best model based on RMSE
best_model_name = min(results, key=lambda x: results[x]["metrics"]["rmse"])
best_model_data = results[best_model_name]

print(f"\n✓ Best Model: {best_model_name}")
print(f"  RMSE: {best_model_data['metrics']['rmse']:.2f}")
print(f"  R²: {best_model_data['metrics']['r2']:.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Register Best Model

# COMMAND ----------

# Register the best model in Unity Catalog
model_uri = f"runs:/{best_model_data['run_id']}/model"
full_model_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}"

registered_model = mlflow.register_model(
    model_uri=model_uri,
    name=full_model_name
)

print(f"✓ Model registered: {registered_model.name}")
print(f"  Version: {registered_model.version}")

# Set alias for production
client = mlflow.tracking.MlflowClient()
client.set_registered_model_alias(
    name=full_model_name,
    alias="production",
    version=registered_model.version
)
print("✓ Set 'production' alias")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Deploy to Model Serving Endpoint

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput

w = WorkspaceClient()

# Check if endpoint exists and update or create
try:
    existing = w.serving_endpoints.get(ENDPOINT_NAME)
    print(f"Updating existing endpoint '{ENDPOINT_NAME}'...")
    
    w.serving_endpoints.update_config_and_wait(
        name=ENDPOINT_NAME,
        served_entities=[
            ServedEntityInput(
                entity_name=full_model_name,
                entity_version=str(registered_model.version),
                workload_size="Small",
                scale_to_zero_enabled=True
            )
        ]
    )
except Exception as e:
    if "ResourceDoesNotExist" in str(e) or "does not exist" in str(e).lower():
        print(f"Creating new endpoint '{ENDPOINT_NAME}'...")
        
        w.serving_endpoints.create_and_wait(
            name=ENDPOINT_NAME,
            config=EndpointCoreConfigInput(
                name=ENDPOINT_NAME,
                served_entities=[
                    ServedEntityInput(
                        entity_name=full_model_name,
                        entity_version=str(registered_model.version),
                        workload_size="Small",
                        scale_to_zero_enabled=True
                    )
                ]
            )
        )
    else:
        raise e

print(f"✓ Model serving endpoint '{ENDPOINT_NAME}' is ready!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Test the Endpoint

# COMMAND ----------

# Poll the endpoint until it reports READY before querying. create_and_wait /
# update_config_and_wait return when the config update is applied, but the
# served-model can still be spinning up — a fixed time.sleep(10) then query
# races that and throws NotFound/503. Poll config_update + ready state, then
# retry the query a few times.
import time
from databricks.sdk.service.serving import EndpointStateReady, EndpointStateConfigUpdate

def _wait_endpoint_ready(name, timeout_s=600, interval_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        state = w.serving_endpoints.get(name).state
        ready = state and state.ready == EndpointStateReady.READY
        settled = not state or state.config_update != EndpointStateConfigUpdate.IN_PROGRESS
        if ready and settled:
            return True
        time.sleep(interval_s)
    return False

if not _wait_endpoint_ready(ENDPOINT_NAME):
    print(f"⚠ Endpoint '{ENDPOINT_NAME}' not READY within timeout — attempting query anyway")

# Create test input
test_features = X_test.iloc[:3].to_dict(orient='records')

print("Test input (first 3 samples):")
print(pd.DataFrame(test_features))

# Query endpoint (retry to absorb the brief warm-up window after READY)
response = None
for _attempt in range(5):
    try:
        response = w.serving_endpoints.query(
            name=ENDPOINT_NAME,
            dataframe_records=test_features
        )
        break
    except Exception as _e:
        print(f"  query attempt {_attempt + 1} failed ({_e}); retrying in 15s…")
        time.sleep(15)

if response is None:
    raise RuntimeError(f"Endpoint '{ENDPOINT_NAME}' did not answer a test query after retries")

print(f"\nPredictions: {response.predictions}")
print(f"Actual values: {y_test.iloc[:3].tolist()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Save Feature Importance Analysis

# COMMAND ----------

# Get feature importance from best model
if best_model_name == "LightGBM":
    importance = best_model_data["model"].feature_importances_
elif best_model_name == "XGBoost":
    importance = best_model_data["model"].feature_importances_
else:
    importance = best_model_data["model"].feature_importances_

importance_df = pd.DataFrame({
    "feature": X_train.columns,
    "importance": importance
}).sort_values("importance", ascending=False)

# Save to Delta table
importance_spark_df = spark.createDataFrame(importance_df)
importance_spark_df.write.mode("overwrite").saveAsTable("demand_forecast_feature_importance")

print("\n" + "="*50)
print("FEATURE IMPORTANCE (Top 15)")
print("="*50)
for i, row in importance_df.head(15).iterrows():
    bar = "█" * int(row['importance'] / importance_df['importance'].max() * 30)
    print(f"{row['feature']:25} {bar} {row['importance']:.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("="*70)
print("DEMAND FORECAST MODEL - TRAINING COMPLETE")
print("="*70)
print(f"""
Model Details:
  • Best Algorithm: {best_model_name}
  • RMSE: {best_model_data['metrics']['rmse']:.2f} transactions/day
  • R² Score: {best_model_data['metrics']['r2']:.4f}
  • MAPE: {best_model_data['metrics']['mape']:.2f}%

Deployment:
  • Model: {full_model_name}
  • Version: {registered_model.version}
  • Endpoint: {ENDPOINT_NAME}
  • Status: Ready for inference

Features Used ({len(X_train.columns)}):
  • Temporal: day_of_week, month, is_weekend, etc.
  • Lag: txn_lag_1, txn_lag_7, revenue_lag_1, etc.
  • Rolling: 7-day avg, 14-day avg, 7-day std
  • Store: store_id

Next Steps:
  1. Run notebook 03_train_labor_optimization_model.py
  2. The endpoint is ready for the StoreSight IQ app
""")
print("="*70)
