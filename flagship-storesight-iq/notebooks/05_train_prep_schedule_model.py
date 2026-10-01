# Databricks notebook source
# MAGIC %md
# MAGIC # StoreSight IQ - Prep Schedule Model
# MAGIC
# MAGIC This notebook trains a regression model to predict optimal prep quantities:
# MAGIC 1. Feature engineering from traffic patterns and prep-subtype properties
# MAGIC 2. Train multiple regressors (LightGBM, XGBoost, Random Forest)
# MAGIC 3. Compare performance and select best model
# MAGIC 4. Register in MLflow and deploy to Model Serving
# MAGIC
# MAGIC **Task Type:** Regression (predict optimal quantity per prep pull)
# MAGIC
# MAGIC **Models trained:**
# MAGIC - LightGBM Regressor (fast training on mixed features)
# MAGIC - XGBoost Regressor (handles non-linear patterns)
# MAGIC - Random Forest Regressor (robust baseline)
# MAGIC
# MAGIC **Domain Knowledge Applied:**
# MAGIC - Prepped-item usable windows (per subtype)
# MAGIC - Prep times per subtype
# MAGIC - Daypart demand patterns (from the domain taxonomy)
# MAGIC
# MAGIC **Prerequisites:** Run notebooks 01-04 first

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

# Parameterized via the DAB job / notebook widgets (no hardcoded customer values).
dbutils.widgets.text("catalog", "publix_labor_forecast")
dbutils.widgets.text("schema", "storesight_iq_publix")
dbutils.widgets.text("resource_prefix", "storesight-publix")
dbutils.widgets.text("domain_json_path", "")

CATALOG_NAME = dbutils.widgets.get("catalog")
SCHEMA_NAME = dbutils.widgets.get("schema")
PREFIX = dbutils.widgets.get("resource_prefix")
MODEL_NAME = f"{PREFIX.replace('-', '_')}_prep_scheduler"
ENDPOINT_NAME = f"{PREFIX}-prep-scheduler"

TEST_SIZE = 0.2
RANDOM_STATE = 42

# --- Load the single-source domain taxonomy (config/domain.json) ---
import json as _json
import os as _os

def _load_domain():
    candidates = []
    _wp = dbutils.widgets.get("domain_json_path")
    if _wp:
        candidates.append(_wp)
    candidates += [
        "config/domain.json", "../config/domain.json", "./config/domain.json",
        _os.path.join(_os.getcwd(), "config", "domain.json"),
        _os.path.join(_os.path.dirname(_os.getcwd()), "config", "domain.json"),
    ]
    for p in candidates:
        try:
            if p and _os.path.exists(p):
                with open(p) as f:
                    return _json.load(f)
        except Exception:
            pass
    raise FileNotFoundError(
        "config/domain.json not found. Pass the 'domain_json_path' widget "
        "(the DAB sets this to the synced repo path)."
    )

DOMAIN = _load_domain()
OPERATING = DOMAIN["operating_hours"]
DAYPARTS = DOMAIN["dayparts"]
RUSH = DOMAIN["rush_hours"]

# Prep-subtype properties (must match services/model_serving.py SUBTYPE_SPECS).
# Shape kept as {key: {id, bake_time, freshness_hours, popularity}}; `bake_time`
# holds the domain prep_time_min. The trained feature KEY names (crust_id,
# bake_time_min, ...) are retained downstream so the ML contract does not drift.
CRUST_TYPES = {
    s["key"]: {
        "id": s["id"],
        "bake_time": s["prep_time_min"],
        "freshness_hours": s["freshness_hours"],
        "popularity": s["popularity"],
    }
    for s in DOMAIN["prep"]["subtypes"]
}


def _daypart_for(hour):
    for dp in DAYPARTS:
        if dp["start"] <= hour < dp["end"]:
            return dp
    return None

# COMMAND ----------

spark.sql(f"USE CATALOG {CATALOG_NAME}")
spark.sql(f"USE SCHEMA {SCHEMA_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load Traffic Pattern Data

# COMMAND ----------

# Load transaction data for traffic patterns
transactions = spark.table("pos_transactions")

# Get hourly traffic by store
hourly_traffic = transactions.groupBy(
    "store_id",
    F.date_format("timestamp", "yyyy-MM-dd").alias("date"),
    F.hour("timestamp").alias("hour")
).agg(
    F.count("*").alias("transactions")
)

# Add day of week
hourly_traffic = hourly_traffic.withColumn("date_parsed", F.to_date("date"))
hourly_traffic = hourly_traffic.withColumn("day_of_week", F.dayofweek("date_parsed"))
hourly_traffic = hourly_traffic.withColumn("is_weekend", 
    F.when(F.col("day_of_week").isin([1, 7]), 1).otherwise(0))

print(f"Hourly traffic records: {hourly_traffic.count():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create Training Dataset
# MAGIC 
# MAGIC Generate training data combining:
# MAGIC - Traffic patterns by hour
# MAGIC - Prep-subtype properties
# MAGIC - Daypart-specific demand factors (from the domain taxonomy)

# COMMAND ----------

# Convert to Pandas for data generation
traffic_pdf = hourly_traffic.toPandas()

# Generate training records
training_records = []

for _, row in traffic_pdf.iterrows():
    store_id = row['store_id']
    hour = row['hour']
    traffic = row['transactions']
    day_of_week = row['day_of_week']
    is_weekend = row['is_weekend']

    # Skip hours outside operating range (from the domain taxonomy)
    if hour < OPERATING["open"] or hour >= OPERATING["close"]:
        continue

    # Daypart factors — sourced from the domain taxonomy; MUST match
    # services/model_serving.py predict_prep_schedule (which reads the same source).
    _dp = _daypart_for(hour)
    if _dp is None:
        continue
    daypart = _dp["name"]
    daypart_encoded = _dp["encoded"]
    daypart_factor = _dp["factor"]

    # For each prep subtype
    for crust_name, props in CRUST_TYPES.items():
        # Optimal prep quantity based on traffic and subtype popularity
        # Formula: traffic * subtype_popularity * usage_rate * freshness_adjustment
        base_qty = traffic * props["popularity"] * 0.9  # prep attach rate

        # Adjust for usable window (shorter window = prep more frequently, smaller batches)
        freshness_factor = 6 / props["freshness_hours"]  # Normalized to 6-hour reference

        # Weight by daypart demand
        base_qty = base_qty * (1 + daypart_factor)

        # Optimal quantity (rounded, with min/max bounds)
        optimal_qty = max(5, min(45, int(base_qty * freshness_factor)))

        # Add some realistic variation
        optimal_qty = int(optimal_qty * np.random.uniform(0.9, 1.1))

        training_records.append({
            "store_id": store_id,
            "hour": hour,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "traffic": traffic,
            "daypart_encoded": daypart_encoded,
            "daypart_factor": daypart_factor,
            "crust_id": props["id"],
            "bake_time_min": props["bake_time"],
            "freshness_hours": props["freshness_hours"],
            "popularity": props["popularity"],
            "optimal_quantity": optimal_qty
        })

train_pdf = pd.DataFrame(training_records)
print(f"Training records: {len(train_pdf):,}")
print(f"\nSample data:")
print(train_pdf.head(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Feature Engineering

# COMMAND ----------

# Add derived features
train_pdf["traffic_per_hour_normalized"] = train_pdf["traffic"] / train_pdf["traffic"].max()
# Rush-hour window from the domain taxonomy (must match services/model_serving.py domain.is_rush_hour)
train_pdf["is_rush_hour"] = ((train_pdf["hour"] >= RUSH["start"]) & (train_pdf["hour"] <= RUSH["end"])).astype(int)
train_pdf["bake_complexity"] = train_pdf["bake_time_min"] / 30  # Normalized bake time
train_pdf["freshness_urgency"] = 1 / train_pdf["freshness_hours"]  # Higher = needs more frequent prep

# Feature columns — order/names MUST match services/model_serving.py predict_prep_schedule
feature_cols = [
    "store_id", "hour", "day_of_week", "is_weekend",
    "traffic", "traffic_per_hour_normalized",
    "daypart_encoded", "daypart_factor",
    "is_rush_hour",
    "crust_id", "bake_time_min", "freshness_hours", "popularity",
    "bake_complexity", "freshness_urgency"
]

X = train_pdf[feature_cols]
y = train_pdf["optimal_quantity"]

print(f"\nFeatures: {len(feature_cols)}")
print(f"Target range: {y.min()} - {y.max()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Train/Test Split

# COMMAND ----------

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
)

print(f"Training: {len(X_train):,} | Test: {len(X_test):,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Train Regression Models

# COMMAND ----------

experiment_name = f"/Users/{spark.sql('SELECT current_user()').first()[0]}/{MODEL_NAME}"
mlflow.set_experiment(experiment_name)

def evaluate_regressor(model, X_test, y_test, model_name):
    """Evaluate regression model for prep scheduling."""
    y_pred = model.predict(X_test)

    # Round predictions (can't prep fractional items)
    y_pred = np.round(y_pred).clip(5, 45)  # Min 5, max 45 items per prep

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # Within 2 items accuracy (practical metric for prep)
    within_2 = np.mean(np.abs(y_test - y_pred) <= 2)

    print(f"\n{model_name} Results:")
    print(f"  RMSE: {rmse:.2f} items")
    print(f"  MAE:  {mae:.2f} items")
    print(f"  R²:   {r2:.4f}")
    print(f"  Within ±2 items: {within_2:.2%}")

    return {"rmse": rmse, "mae": mae, "r2": r2, "within_2": within_2}

results = {}

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model 1: LightGBM Regressor
# MAGIC 
# MAGIC Fast training, handles categorical features well

# COMMAND ----------

print("Training LightGBM Regressor...")
start_time = time.time()

with mlflow.start_run(run_name="LightGBM_PrepScheduler") as run:
    lgb_params = {
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "max_depth": 6,
        "learning_rate": 0.05,
        "n_estimators": 300,
        "min_child_samples": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "random_state": RANDOM_STATE,
        "verbose": -1
    }
    
    lgb_model = lgb.LGBMRegressor(**lgb_params)
    lgb_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
    )
    
    train_time = time.time() - start_time
    metrics = evaluate_regressor(lgb_model, X_test, y_test, "LightGBM")
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
# MAGIC ### Model 2: XGBoost Regressor
# MAGIC 
# MAGIC Captures non-linear patterns in prep demand

# COMMAND ----------

print("Training XGBoost Regressor...")
start_time = time.time()

with mlflow.start_run(run_name="XGBoost_PrepScheduler") as run:
    xgb_params = {
        "objective": "reg:squarederror",
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
    
    xgb_model = xgb.XGBRegressor(**xgb_params)
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    train_time = time.time() - start_time
    metrics = evaluate_regressor(xgb_model, X_test, y_test, "XGBoost")
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
# MAGIC ### Model 3: Random Forest Regressor
# MAGIC 
# MAGIC Robust baseline, good for interpretability

# COMMAND ----------

print("Training Random Forest Regressor...")
start_time = time.time()

with mlflow.start_run(run_name="RandomForest_PrepScheduler") as run:
    rf_params = {
        "n_estimators": 200,
        "max_depth": 10,
        "min_samples_split": 10,
        "min_samples_leaf": 5,
        "max_features": "sqrt",
        "random_state": RANDOM_STATE,
        "n_jobs": -1
    }
    
    rf_model = RandomForestRegressor(**rf_params)
    rf_model.fit(X_train, y_train)
    
    train_time = time.time() - start_time
    metrics = evaluate_regressor(rf_model, X_test, y_test, "Random Forest")
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
        "RMSE": f"{m['rmse']:.2f}",
        "MAE": f"{m['mae']:.2f}",
        "R²": f"{m['r2']:.4f}",
        "Within ±2": f"{m['within_2']:.2%}",
        "Time": f"{m['train_time']:.1f}s"
    })

comparison_df = pd.DataFrame(comparison_data)
print("\n" + "="*70)
print("MODEL COMPARISON - Prep Schedule (Regression)")
print("="*70)
print(comparison_df.to_string(index=False))
print("="*70)

# Select best model based on RMSE
best_model_name = min(results, key=lambda x: results[x]["metrics"]["rmse"])
best_model_data = results[best_model_name]

print(f"\n✓ Best Model: {best_model_name}")
print(f"  RMSE: {best_model_data['metrics']['rmse']:.2f} items")
print(f"  Within ±2 items: {best_model_data['metrics']['within_2']:.2%}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Feature Importance Analysis

# COMMAND ----------

# Get feature importance
importance = best_model_data["model"].feature_importances_
importance_df = pd.DataFrame({
    "feature": X_train.columns,
    "importance": importance
}).sort_values("importance", ascending=False)

print("\n" + "="*50)
print("FEATURE IMPORTANCE")
print("="*50)
for _, row in importance_df.iterrows():
    bar = "█" * int(row['importance'] / importance_df['importance'].max() * 25)
    print(f"  {row['feature']:28} {bar} {row['importance']:.4f}")

# Key insight
top_features = importance_df.head(5)['feature'].tolist()
print(f"\n✓ Top predictors: {', '.join(top_features)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Sample Predictions

# COMMAND ----------

# Show sample predictions for each crust type
sample_idx = X_test.sample(n=15, random_state=42).index
sample_X = X_test.loc[sample_idx]
sample_y = y_test.loc[sample_idx]
sample_pred = np.round(best_model_data["model"].predict(sample_X)).astype(int)

# Map crust_id back to name
crust_names = {v["id"]: k for k, v in CRUST_TYPES.items()}

sample_results = pd.DataFrame({
    "Hour": sample_X["hour"].values,
    "Traffic": sample_X["traffic"].values,
    "Subtype": [crust_names.get(int(b), "?") for b in sample_X["crust_id"]],
    "Actual": sample_y.values,
    "Predicted": sample_pred,
    "Diff": sample_pred - sample_y.values
})

print("\nSample Predictions:")
print(sample_results.to_string(index=False))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Register and Deploy

# COMMAND ----------

# Register model
model_uri = f"runs:/{best_model_data['run_id']}/model"
full_model_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}"

registered_model = mlflow.register_model(model_uri=model_uri, name=full_model_name)
print(f"✓ Registered: {registered_model.name} v{registered_model.version}")

# Set production alias
client = mlflow.tracking.MlflowClient()
client.set_registered_model_alias(name=full_model_name, alias="production", version=registered_model.version)

# COMMAND ----------

# Deploy to Model Serving
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
print("PREP SCHEDULE MODEL - TRAINING COMPLETE")
print("="*70)
print(f"""
Model Details:
  • Task: Regression (Predict optimal items per prep)
  • Best Algorithm: {best_model_name}
  • RMSE: {best_model_data['metrics']['rmse']:.2f} items
  • Within ±2 items: {best_model_data['metrics']['within_2']:.2%}

Prep Subtypes Supported (from the domain taxonomy):

Deployment:
  • Model: {full_model_name}
  • Version: {registered_model.version}
  • Endpoint: {ENDPOINT_NAME}

Features Used ({len(X_train.columns)}):
  • Temporal: hour, day_of_week, is_weekend, is_rush_hour
  • Traffic: transactions, traffic_normalized
  • Daypart: daypart_encoded, daypart_factor
  • Subtype: crust_id, bake_time_min, freshness_hours, popularity

Next: Run notebook 06_setup_genie_space.py
""")
print("="*70)
