# Databricks notebook source
# MAGIC %md
# MAGIC # StoreSight IQ - Inventory Prediction Model
# MAGIC 
# MAGIC This notebook trains a regression model to predict optimal reorder quantities:
# MAGIC 1. Feature engineering from inventory and sales patterns
# MAGIC 2. Train multiple regressors (LightGBM, XGBoost, Gradient Boosting)
# MAGIC 3. Compare performance and select best model
# MAGIC 4. Register in MLflow and deploy to Model Serving
# MAGIC 
# MAGIC **Task Type:** Regression (predict suggested order quantity)
# MAGIC 
# MAGIC **Models trained:**
# MAGIC - LightGBM Regressor (fast, accurate for inventory data)
# MAGIC - XGBoost Regressor (robust, handles outliers)
# MAGIC - Gradient Boosting Regressor (sklearn's implementation)
# MAGIC 
# MAGIC **Prerequisites:** Run notebooks 01-03 first

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
from sklearn.ensemble import GradientBoostingRegressor
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
MODEL_NAME = f"{PREFIX.replace('-', '_')}_inventory_predictor"
ENDPOINT_NAME = f"{PREFIX}-inventory-predictor"

TEST_SIZE = 0.2
RANDOM_STATE = 42

# COMMAND ----------

spark.sql(f"USE CATALOG {CATALOG_NAME}")
spark.sql(f"USE SCHEMA {SCHEMA_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load and Prepare Data

# COMMAND ----------

# Load inventory and ingredient data
inventory = spark.table("inventory_levels")
ingredients = spark.table("ingredients")

# Join to get ingredient details
inventory_with_details = inventory.join(ingredients, "ingredient_id")

print(f"Inventory records: {inventory_with_details.count():,}")
inventory_with_details.show(5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Feature Engineering for Inventory Prediction
# MAGIC 
# MAGIC Key features for inventory prediction:
# MAGIC - Current stock level vs par level
# MAGIC - Days of supply remaining
# MAGIC - Ingredient category (affects turnover rate)
# MAGIC - Historical usage patterns

# COMMAND ----------

# Calculate derived features
training_data = inventory_with_details.withColumn(
    "stock_ratio", F.col("qty_on_hand") / F.col("par_level")
)

training_data = training_data.withColumn(
    "below_par", F.when(F.col("qty_on_hand") < F.col("par_level"), 1).otherwise(0)
)

training_data = training_data.withColumn(
    "critical_level", F.when(F.col("days_supply") < 2, 1).otherwise(0)
)

# Simulate daily usage rate (par_level / 3 days is typical turnover)
training_data = training_data.withColumn(
    "daily_usage_rate", F.col("par_level") / 3
)

# Calculate ideal order quantity
# If stock < par, order enough to get to par + 20% buffer
training_data = training_data.withColumn(
    "suggested_order_qty",
    F.when(F.col("qty_on_hand") < F.col("par_level"),
           F.col("par_level") * 1.2 - F.col("qty_on_hand")
    ).otherwise(0)
)

# Category encoding (numeric for ML) — sourced from the domain taxonomy
# (config/domain.json). MUST match services/model_serving.py CATEGORY_ENCODING,
# which reads the same single source, so the feature contract cannot drift.
import json as _json
import os as _os

def _load_domain():
    cands = []
    _wp = dbutils.widgets.get("domain_json_path")
    if _wp:
        cands.append(_wp)
    cands += [
        "config/domain.json", "../config/domain.json", "./config/domain.json",
        _os.path.join(_os.getcwd(), "config", "domain.json"),
        _os.path.join(_os.path.dirname(_os.getcwd()), "config", "domain.json"),
    ]
    for p in cands:
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

_domain = _load_domain()
category_map = _domain["ingredient_categories"]
# Fleet size drives the store_id normalization feature (was a hardcoded 25).
NUM_STORES = max(len(_domain.get("stores", [])), 1)
_UNKNOWN_CATEGORY = (max(category_map.values()) + 1) if category_map else 8

from pyspark.sql.types import IntegerType

@F.udf(IntegerType())
def encode_category(cat):
    return category_map.get(cat, _UNKNOWN_CATEGORY)

training_data = training_data.withColumn("category_encoded", encode_category(F.col("category")))

# Store features
training_data = training_data.withColumn("store_normalized", F.col("store_id") / float(NUM_STORES))

print("Features created:")
training_data.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Create Expanded Training Dataset
# MAGIC 
# MAGIC Simulate multiple scenarios per ingredient for robust training

# COMMAND ----------

# Expand dataset by simulating different stock levels
from pyspark.sql import Row

# Get unique store-ingredient combinations
base_data = training_data.select(
    "store_id", "ingredient_id", "par_level", "category_encoded", "cost_per_unit"
).distinct()

# Create expanded scenarios
scenarios = []
for row in base_data.collect():
    store_id = row.store_id
    ing_id = row.ingredient_id
    par = row.par_level
    cat = row.category_encoded
    cost = row.cost_per_unit
    
    # Simulate various stock levels (10% to 150% of par)
    for stock_pct in np.arange(0.1, 1.6, 0.1):
        stock = par * stock_pct
        days_supply = stock / (par / 3) if par > 0 else 0
        
        # Calculate target order quantity
        if stock < par:
            suggested_qty = max(0, par * 1.2 - stock)
        else:
            suggested_qty = 0
        
        scenarios.append({
            "store_id": store_id,
            "ingredient_id": ing_id,
            "par_level": float(par),
            "category_encoded": cat,
            "cost_per_unit": float(cost),
            "qty_on_hand": float(stock),
            "days_supply": float(days_supply),
            "stock_ratio": float(stock_pct),
            "below_par": 1 if stock < par else 0,
            "critical_level": 1 if days_supply < 2 else 0,
            "daily_usage_rate": float(par / 3),
            "suggested_order_qty": float(suggested_qty)
        })

# Create DataFrame
scenarios_df = spark.createDataFrame(scenarios)
print(f"Training scenarios: {scenarios_df.count():,}")

# Convert to Pandas
train_pdf = scenarios_df.toPandas()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Train/Test Split

# COMMAND ----------

from sklearn.model_selection import train_test_split

# Features and target
feature_cols = [
    "store_id", "ingredient_id", "par_level", "category_encoded", "cost_per_unit",
    "qty_on_hand", "days_supply", "stock_ratio", "below_par", "critical_level",
    "daily_usage_rate"
]

X = train_pdf[feature_cols]
y = train_pdf["suggested_order_qty"]

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
    """Evaluate regression model."""
    y_pred = model.predict(X_test)
    
    # Clip negative predictions to 0 (can't order negative quantity)
    y_pred = np.maximum(y_pred, 0)
    
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    # Mean Absolute Percentage Error (avoiding division by zero)
    mask = y_test > 0
    mape = np.mean(np.abs((y_test[mask] - y_pred[mask]) / y_test[mask])) * 100 if mask.sum() > 0 else 0
    
    print(f"\n{model_name} Results:")
    print(f"  RMSE: {rmse:.2f} units")
    print(f"  MAE:  {mae:.2f} units")
    print(f"  R²:   {r2:.4f}")
    print(f"  MAPE: {mape:.2f}%")
    
    return {"rmse": rmse, "mae": mae, "r2": r2, "mape": mape}

results = {}

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model 1: LightGBM Regressor
# MAGIC 
# MAGIC Optimized for inventory data with mixed feature types

# COMMAND ----------

print("Training LightGBM Regressor...")
start_time = time.time()

with mlflow.start_run(run_name="LightGBM_Inventory") as run:
    lgb_params = {
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "max_depth": 8,
        "learning_rate": 0.05,
        "n_estimators": 400,
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
# MAGIC Robust to outliers and missing values

# COMMAND ----------

print("Training XGBoost Regressor...")
start_time = time.time()

with mlflow.start_run(run_name="XGBoost_Inventory") as run:
    xgb_params = {
        "objective": "reg:squarederror",
        "max_depth": 8,
        "learning_rate": 0.05,
        "n_estimators": 400,
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
# MAGIC ### Model 3: Gradient Boosting Regressor (sklearn)
# MAGIC 
# MAGIC Solid baseline with good interpretability

# COMMAND ----------

print("Training Gradient Boosting Regressor...")
start_time = time.time()

with mlflow.start_run(run_name="GradientBoosting_Inventory") as run:
    gb_params = {
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.05,
        "min_samples_split": 10,
        "min_samples_leaf": 5,
        "subsample": 0.8,
        "random_state": RANDOM_STATE
    }
    
    gb_model = GradientBoostingRegressor(**gb_params)
    gb_model.fit(X_train, y_train)
    
    train_time = time.time() - start_time
    metrics = evaluate_regressor(gb_model, X_test, y_test, "Gradient Boosting")
    metrics["train_time"] = train_time
    results["GradientBoosting"] = {"model": gb_model, "run_id": run.info.run_id, "metrics": metrics}
    
    mlflow.log_params(gb_params)
    mlflow.log_metrics(metrics)
    
    # Create signature for Unity Catalog (required)
    predictions = gb_model.predict(X_train[:100])
    signature = infer_signature(X_train[:100], predictions)
    # serialization_format="cloudpickle": MLflow 3.14 defaults sklearn logging to
    # skops, which rejects tree-based estimators. cloudpickle keeps the classic,
    # load-compatible serialization.
    mlflow.sklearn.log_model(gb_model, "model", signature=signature, serialization_format="cloudpickle")

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
        "MAPE": f"{m['mape']:.2f}%",
        "Time": f"{m['train_time']:.1f}s"
    })

comparison_df = pd.DataFrame(comparison_data)
print("\n" + "="*70)
print("MODEL COMPARISON - Inventory Prediction (Regression)")
print("="*70)
print(comparison_df.to_string(index=False))
print("="*70)

# Select best model based on RMSE
best_model_name = min(results, key=lambda x: results[x]["metrics"]["rmse"])
best_model_data = results[best_model_name]

print(f"\n✓ Best Model: {best_model_name}")
print(f"  RMSE: {best_model_data['metrics']['rmse']:.2f} units")
print(f"  R²: {best_model_data['metrics']['r2']:.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Feature Importance

# COMMAND ----------

# Get feature importance from best model
if hasattr(best_model_data["model"], "feature_importances_"):
    importance = best_model_data["model"].feature_importances_
    importance_df = pd.DataFrame({
        "feature": X_train.columns,
        "importance": importance
    }).sort_values("importance", ascending=False)
    
    print("\nFeature Importance:")
    for _, row in importance_df.iterrows():
        bar = "█" * int(row['importance'] / importance_df['importance'].max() * 25)
        print(f"  {row['feature']:20} {bar} {row['importance']:.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Register and Deploy

# COMMAND ----------

# Register model
model_uri = f"runs:/{best_model_data['run_id']}/model"
full_model_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}"

registered_model = mlflow.register_model(model_uri=model_uri, name=full_model_name)
print(f"✓ Registered: {registered_model.name} v{registered_model.version}")

client = mlflow.tracking.MlflowClient()
client.set_registered_model_alias(name=full_model_name, alias="production", version=registered_model.version)

# Deploy to serving
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput

w = WorkspaceClient()

try:
    w.serving_endpoints.get(ENDPOINT_NAME)
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
print("INVENTORY PREDICTION MODEL - TRAINING COMPLETE")
print("="*70)
print(f"""
Model Details:
  • Task: Regression (Predict order quantity)
  • Best Algorithm: {best_model_name}
  • RMSE: {best_model_data['metrics']['rmse']:.2f} units
  • R² Score: {best_model_data['metrics']['r2']:.4f}

Deployment:
  • Model: {full_model_name}
  • Version: {registered_model.version}
  • Endpoint: {ENDPOINT_NAME}

Features Used ({len(X_train.columns)}):
  • Stock: qty_on_hand, par_level, stock_ratio, days_supply
  • Status: below_par, critical_level
  • Ingredient: category_encoded, cost_per_unit
  • Usage: daily_usage_rate

Next: Run notebook 05_train_prep_schedule_model.py (prep-schedule model)
""")
print("="*70)
