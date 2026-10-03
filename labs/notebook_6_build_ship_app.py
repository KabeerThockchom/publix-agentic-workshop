# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 6 - Build and Ship an App
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** Deploy a governed Databricks App that queries your gold table in your catalog. ~45 minutes.
# MAGIC
# MAGIC You have two paths: **Path A** uses App Builder (simpler, UI-driven), **Path B** uses Databricks CLI +
# MAGIC manual development (more control, local dev loop). Both deploy via Databricks Asset Bundles.
# MAGIC
# MAGIC Why not Genie Code for app generation? LLMs struggle with multi-file frontends and build systems.
# MAGIC Genie Code excels at SQL/logic; hand-built app shells are cleaner and more maintainable.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Your Catalog
# MAGIC
# MAGIC You all share one workspace, so each participant builds in their OWN catalog.
# MAGIC Run the next cell and type your first name in the `my_name` box that appears at the top.

# COMMAND ----------

dbutils.widgets.text("my_name", "", "Your first name (lowercase, no spaces)")
name = dbutils.widgets.get("my_name")
assert name and " " not in name, "Type your first name (lowercase, no spaces) in the my_name box at the top, then re-run."
CATALOG = f"publix_agentic_{name}"
print(f"Your catalog: {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will build
# MAGIC
# MAGIC A **Store & Item Insights** Databricks App that queries your gold table
# MAGIC (your own `publix_agentic_<yourname>.medallion.gold_store_item_daily`). Show top-selling items by store,
# MAGIC let users filter by store and date range, all SQL-backed and governed.
# MAGIC
# MAGIC **Two paths to the same result:**
# MAGIC - **Path A: App Builder (beta)** - Point-and-click configuration, no code, UI-driven
# MAGIC - **Path B: Databricks CLI + Manual Dev** - Full control, local development loop, CI/CD-friendly
# MAGIC
# MAGIC Both deploy via Databricks Asset Bundles.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Path A: App Builder (Beta)
# MAGIC
# MAGIC If your workspace has App Builder enabled (check the Create button in Workspace):
# MAGIC
# MAGIC 1. **Click Create > App** in the Workspace UI
# MAGIC 2. **Name it** `store-item-insights`
# MAGIC 3. **Choose Mode:** Select "snapshot" (static query) or "interactive" (with parameters)
# MAGIC 4. **Wire to warehouse** - Select `publix-workshop-wh` as your SQL warehouse
# MAGIC 5. **Add your query** (replace `publix_agentic_workshop` with your own `publix_agentic_<yourname>`):
# MAGIC    ```sql
# MAGIC    SELECT
# MAGIC      store_number, item_sku, item_name, item_family,
# MAGIC      sales_date, units_sold, revenue, line_item_count
# MAGIC    FROM publix_agentic_<yourname>.medallion.gold_store_item_daily
# MAGIC    WHERE sales_date >= CURRENT_DATE - 30
# MAGIC    ORDER BY revenue DESC
# MAGIC    LIMIT 100
# MAGIC    ```
# MAGIC 6. **Preview** - App Builder will render a simple table UI
# MAGIC 7. **Publish** - Click Publish; the app gets a shareable URL

# COMMAND ----------

# MAGIC %md
# MAGIC ## Path B: Databricks CLI + Manual Dev
# MAGIC
# MAGIC For teams who want a local development loop:
# MAGIC
# MAGIC ### Setup
# MAGIC
# MAGIC ```bash
# MAGIC # Authenticate your local Databricks CLI
# MAGIC databricks auth login --host https://adb-<workspace-id>.<region>.azuredatabricks.net --profile publix-ws
# MAGIC
# MAGIC # Clone your team repo (or init a new one)
# MAGIC git clone https://your-team-repo.git
# MAGIC cd store-insights-app
# MAGIC
# MAGIC # Create app directory
# MAGIC mkdir -p apps/store-item-insights/{backend,frontend,src}
# MAGIC ```
# MAGIC
# MAGIC ### Backend (FastAPI)
# MAGIC
# MAGIC Create `apps/store-item-insights/backend/main.py`:
# MAGIC
# MAGIC ```python
# MAGIC from fastapi import FastAPI
# MAGIC from databricks.sql import connect
# MAGIC import os
# MAGIC
# MAGIC app = FastAPI()
# MAGIC
# MAGIC @app.get("/api/top-items")
# MAGIC def top_items(store_id: str = None, limit: int = 20):
# MAGIC    """Query the gold table for top items by revenue."""
# MAGIC    with connect(host=os.getenv("DATABRICKS_HOST"),
# MAGIC                  token=os.getenv("DATABRICKS_TOKEN"),
# MAGIC                  warehouse_id=os.getenv("WAREHOUSE_ID")) as conn:
# MAGIC        query = """
# MAGIC        SELECT store_number, item_sku, item_name, revenue, units_sold
# MAGIC        FROM publix_agentic_<yourname>.medallion.gold_store_item_daily
# MAGIC        """  # Replace publix_agentic_workshop with your own publix_agentic_<yourname>
# MAGIC        if store_id:
# MAGIC            query += f" WHERE store_number = {store_id}"
# MAGIC        query += " ORDER BY revenue DESC LIMIT " + str(limit)
# MAGIC
# MAGIC        result = conn.execute(query).fetchall()
# MAGIC        return {"items": [dict(row) for row in result]}
# MAGIC ```
# MAGIC
# MAGIC ### Frontend (React)
# MAGIC
# MAGIC Create `apps/store-item-insights/frontend/src/App.tsx`:
# MAGIC
# MAGIC ```typescript
# MAGIC import React, { useEffect, useState } from 'react';
# MAGIC
# MAGIC function App() {
# MAGIC   const [items, setItems] = useState([]);
# MAGIC   const [storeId, setStoreId] = useState('');
# MAGIC
# MAGIC   useEffect(() => {
# MAGIC     fetch('/api/top-items?store_id=' + storeId)
# MAGIC       .then(r => r.json())
# MAGIC       .then(d => setItems(d.items));
# MAGIC   }, [storeId]);
# MAGIC
# MAGIC   return (
# MAGIC     <div>
# MAGIC       <h1>Store & Item Insights</h1>
# MAGIC       <input placeholder=\"Store ID\" onChange={e => setStoreId(e.target.value)} />
# MAGIC       <table>
# MAGIC         <thead><tr><th>Item</th><th>Revenue</th><th>Units</th></tr></thead>
# MAGIC         <tbody>
# MAGIC           {items.map(item => (
# MAGIC             <tr key={item.item_sku}>
# MAGIC               <td>{item.item_name}</td>
# MAGIC               <td>${item.revenue}</td>
# MAGIC               <td>{item.units_sold}</td>
# MAGIC             </tr>
# MAGIC           ))}
# MAGIC         </tbody>
# MAGIC       </table>
# MAGIC     </div>
# MAGIC   );
# MAGIC }
# MAGIC
# MAGIC export default App;
# MAGIC ```
# MAGIC
# MAGIC ### Deploy via DAB
# MAGIC
# MAGIC Create `databricks.yml`:
# MAGIC
# MAGIC ```yaml
# MAGIC bundle:
# MAGIC   name: store-insights-app
# MAGIC   target: dev
# MAGIC
# MAGIC resources:
# MAGIC   apps:
# MAGIC     store-item-insights:
# MAGIC       name: Store & Item Insights
# MAGIC       source_code_path: ./apps/store-item-insights
# MAGIC
# MAGIC targets:
# MAGIC   dev:
# MAGIC     workspace:
# MAGIC       host: https://adb-<workspace-id>.<region>.azuredatabricks.net
# MAGIC ```
# MAGIC
# MAGIC Deploy:
# MAGIC
# MAGIC ```bash
# MAGIC # Validate the bundle
# MAGIC databricks bundle validate
# MAGIC
# MAGIC # Deploy
# MAGIC databricks bundle deploy
# MAGIC
# MAGIC # Get the live URL
# MAGIC databricks apps get store-item-insights
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## After deployment
# MAGIC
# MAGIC - **Share the app URL** with your team or stakeholders
# MAGIC - **Iterate** - modify queries, add filters, improve UI locally and re-deploy
# MAGIC - **Teach** - this template exists in your repo; others can fork it for new dashboards
# MAGIC - **Scale** - same pattern works for any gold table: inventory, pricing, costs, etc.
# MAGIC
# MAGIC **No copy-paste. No manual clicking. Just code, commits, and deployments.**
