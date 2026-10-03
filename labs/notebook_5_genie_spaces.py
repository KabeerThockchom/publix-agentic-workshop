# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 5 - Genie Agents: From Data to Self-Serve
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** Build a production Genie Agent on your gold-layer data so business users can ask questions in plain English. ~20 minutes.
# MAGIC
# MAGIC You now have your own `publix_agentic_<yourname>.medallion.gold_store_item_daily` (from Notebook 4). This notebook makes it self-serve: you will create a Genie space, write instructions, add example questions, test, and enable Genie One routing. Your team can then ask "What drove revenue last week?" and get an answer.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What is a Genie Agent?
# MAGIC
# MAGIC A **Genie Agent** is a curated front door to your data. It sits between your tables and business users:
# MAGIC
# MAGIC - **Tables** - your gold semantic layer
# MAGIC - **Instructions** - domain guidance (what revenue means, time-range interpretation)
# MAGIC - **Example questions** - seed correct SQL patterns and routing
# MAGIC - **Metrics** - track agent usage and quality
# MAGIC
# MAGIC When a user asks a question:
# MAGIC 1. Genie reads your instructions
# MAGIC 2. Matches to example questions for relevance
# MAGIC 3. Generates and runs SQL
# MAGIC 4. Returns results
# MAGIC
# MAGIC You control which tables are visible and what patterns Genie learns.

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
# MAGIC ## Confirm Your Gold Table
# MAGIC
# MAGIC Your data is ready. Verify it exists and has recent data:

# COMMAND ----------

spark.sql(f"""
SELECT count(*) as row_count,
       min(sales_date) as oldest_date,
       max(sales_date) as newest_date
FROM {CATALOG}.medallion.gold_store_item_daily
""").display()

# COMMAND ----------

spark.sql(f"""
SELECT * FROM {CATALOG}.medallion.gold_store_item_daily LIMIT 3
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create a Genie Agent - Two Paths
# MAGIC
# MAGIC **Path 1: Programmatically via the Genie API (best practice - reproducible, version-controlled)**
# MAGIC
# MAGIC Create the space with a service principal via `POST /api/2.0/genie/spaces`, so it lives in code
# MAGIC and deploys the same way every time. The key detail: send `serialized_space` as a **JSON string**
# MAGIC (not a nested object), built to the v2 schema - text fields as arrays, ids as 32-char lowercase hex,
# MAGIC tables sorted by identifier. (This is exactly how our reference "Publix Store Pulse" space was created.)
# MAGIC
# MAGIC ```bash
# MAGIC # body.json = {"serialized_space": "<the v2 space JSON, stringified>"}
# MAGIC databricks api post /api/2.0/genie/spaces --json @body.json --profile <your-profile>
# MAGIC # -> returns the space_id; GET /api/2.0/genie/spaces/{id} to confirm
# MAGIC ```
# MAGIC
# MAGIC Ask Genie Code to build the `serialized_space` payload for you (table, instructions, sample questions),
# MAGIC then commit it and deploy via a Databricks Asset Bundle for a repeatable, SP-owned space.
# MAGIC
# MAGIC **Path 2: Genie UI (quick manual alternative)**
# MAGIC
# MAGIC For a fast one-off, click **Genie** (sidebar) -> **New Space**, name it `Store & Item Sales Agent`,
# MAGIC pick warehouse `publix-workshop-wh`, add table `publix_agentic_<yourname>.medallion.gold_store_item_daily` (use YOUR catalog),
# MAGIC and **Save**. Good for exploring; use Path 1 for anything you want to ship and reproduce.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write Agent Instructions
# MAGIC
# MAGIC Open Genie Code and run this prompt to generate instructions for the agent:
# MAGIC
# MAGIC > **🧞 Genie Code Prompt:**
# MAGIC > ```
# MAGIC > I'm building a Genie Agent for Publix store operations analysts.
# MAGIC > They will ask about daily store and item sales performance.
# MAGIC >
# MAGIC > Table: publix_agentic_<yourname>.medallion.gold_store_item_daily (use YOUR catalog)
# MAGIC > Columns: store_number, item_sku, item_name, item_family,
# MAGIC >          sales_date, num_transactions, units_sold, revenue, line_item_count
# MAGIC >
# MAGIC > Generate comprehensive general instructions that cover:
# MAGIC > - Revenue = total sales in dollars
# MAGIC > - Units = quantity sold; num_transactions = distinct baskets; line_item_count = basket lines
# MAGIC > - Time interpretation (last week, month, quarter)
# MAGIC > - Grocery categories (produce, deli, meat, grocery)
# MAGIC > - Always filter by sales_date when asked about time ranges
# MAGIC > - Aggregate daily data for trend analysis
# MAGIC >
# MAGIC > Format as concise markdown (150-200 words).
# MAGIC > ```
# MAGIC
# MAGIC Paste the result into your agent's **Settings** → **General instructions**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Add Three Sample Questions
# MAGIC
# MAGIC Sample questions teach Genie what kinds of questions to expect. Use this prompt:
# MAGIC
# MAGIC > **🧞 Genie Code Prompt:**
# MAGIC > ```
# MAGIC > Generate 3 certified example questions + exact SQL for a Publix store sales Genie Agent.
# MAGIC >
# MAGIC > Table: publix_agentic_<yourname>.medallion.gold_store_item_daily (use YOUR catalog)
# MAGIC >
# MAGIC > Include:
# MAGIC > 1. Top items by revenue last week
# MAGIC > 2. Revenue by store for the last 7 days
# MAGIC > 3. Week-over-week comparison of produce category revenue
# MAGIC >
# MAGIC > For each: provide the question, exact SQL, and one-line description.
# MAGIC > Use realistic dates (today = current date).
# MAGIC > Format as a table.
# MAGIC > ```
# MAGIC
# MAGIC Add each example question in your agent's **Settings** → **Example questions**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test & Optimize
# MAGIC
# MAGIC In your agent's chat interface, ask these test questions:
# MAGIC
# MAGIC 1. **"What were the top 5 items by revenue last week?"**
# MAGIC    - Expect: item names, categories, revenue totals
# MAGIC 2. **"Show me daily revenue by store for the last 7 days."**
# MAGIC    - Expect: store numbers, dates, and revenue
# MAGIC 3. **"How did produce revenue change week-over-week in September?"**
# MAGIC    - Expect: week 1 vs week 2 totals and percentage change
# MAGIC
# MAGIC If an answer is off, edit the agent's **instructions** or add a clearer example question, then re-test.
# MAGIC This is the real workflow: iterate until Genie generates correct SQL.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Metric Views - "Show, Don't Build"
# MAGIC
# MAGIC Attach a metric view to track agent quality and usage. Metric views are defined via a YAML spec inside a UC view:
# MAGIC
# MAGIC ```sql
# MAGIC -- Replace publix_agentic_workshop with your own publix_agentic_<yourname>
# MAGIC CREATE OR REPLACE VIEW publix_agentic_<yourname>.medallion.store_performance_metric_view
# MAGIC   WITH METRICS LANGUAGE YAML AS $$
# MAGIC version: 1.0
# MAGIC source: publix_agentic_<yourname>.medallion.gold_store_item_daily
# MAGIC dimensions:
# MAGIC   - name: store_number
# MAGIC     expr: store_number
# MAGIC   - name: item_sku
# MAGIC     expr: item_sku
# MAGIC   - name: sales_date
# MAGIC     expr: sales_date
# MAGIC measures:
# MAGIC   - name: total_revenue
# MAGIC     expr: SUM(revenue)
# MAGIC   - name: total_units
# MAGIC     expr: SUM(units_sold)
# MAGIC   - name: avg_units_per_item
# MAGIC     expr: AVG(units_sold)
# MAGIC $$;
# MAGIC ```
# MAGIC
# MAGIC Query the metric view using the MEASURE() function:
# MAGIC
# MAGIC ```sql
# MAGIC -- Replace publix_agentic_workshop with your own publix_agentic_<yourname>
# MAGIC SELECT
# MAGIC   store_number,
# MAGIC   sales_date,
# MAGIC   MEASURE(total_revenue) as revenue,
# MAGIC   MEASURE(total_units) as units
# MAGIC FROM publix_agentic_<yourname>.medallion.store_performance_metric_view
# MAGIC GROUP BY store_number, sales_date;
# MAGIC ```
# MAGIC
# MAGIC This metric view rolls up daily sales into key KPIs. When users ask "What's total revenue this month?",
# MAGIC Genie can use `total_revenue` instead of writing the SUM from scratch. Saves time, ensures consistency.
# MAGIC
# MAGIC **Note:** Deploy metric views via SQL warehouse queries, not via `aitools query` - the latter strips whitespace and breaks YAML indentation.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Ontology & Trust - The One Slide
# MAGIC
# MAGIC Why can business users trust Genie's answers? Because you've defined the semantic layer:
# MAGIC
# MAGIC ```
# MAGIC Relationships:
# MAGIC   store_number (FK) → store master data
# MAGIC   item_sku (FK) → item catalog
# MAGIC   revenue = SUM(total_price) per day per item per store
# MAGIC
# MAGIC Synonyms (Genie uses these to route questions):
# MAGIC   revenue ≈ sales, total_sales, dollars
# MAGIC   units_sold ≈ quantity, units, volume
# MAGIC   num_transactions ≈ transactions, checks, baskets
# MAGIC   line_item_count ≈ scanned lines, basket lines
# MAGIC
# MAGIC Governance:
# MAGIC   All tables filtered by role (store managers see only their store)
# MAGIC   Revenue is audited daily; 24-hour delay
# MAGIC   Categories are certified by merchandising team
# MAGIC ```
# MAGIC
# MAGIC Tag your agent with these relationships in the Genie UI (Settings → Ontology).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Supervisor Agent Pattern (Bonus)
# MAGIC
# MAGIC If you build multiple agents (e.g., one for **Store Sales**, another for **Inventory**, another for **Labor**),
# MAGIC you need a **supervisor** that routes questions to the right agent.
# MAGIC
# MAGIC Databricks' Build Studio (~/Projects/build-studio-ashwin) demonstrates this pattern:
# MAGIC a router agent that reads a question, classifies it, and delegates to the right specialist agent.
# MAGIC
# MAGIC For now: one agent per domain is standard. See the Build Studio repo for multi-agent orchestration patterns.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Enable Genie One (Multi-Space Routing)
# MAGIC
# MAGIC **Genie One** is the enterprise search layer. It discovers and routes to your agent automatically.
# MAGIC
# MAGIC To enable:
# MAGIC 1. In your agent → **Sharing & Access** → make sure it's **Shared** with your team
# MAGIC 2. That's it. Genie One now sees your agent.
# MAGIC
# MAGIC Test it:
# MAGIC - Open workspace **Chat** (top right) → Ask: "What drove revenue last week?"
# MAGIC - Genie One routes to your **Store & Item Sales Agent** automatically
# MAGIC
# MAGIC If routing fails, check:
# MAGIC - Agent is shared with you
# MAGIC - Agent has instructions + example questions
# MAGIC - SQL warehouse is running and you have `CAN USE` permission

# COMMAND ----------

# MAGIC %md
# MAGIC ## Take-Home: Agent Definition Template
# MAGIC
# MAGIC Use this `.geniespace.json` template to build your own agent in a new domain:
# MAGIC
# MAGIC ```json
# MAGIC {
# MAGIC   "version": 2,
# MAGIC   "config": {
# MAGIC     "sample_questions": [
# MAGIC       {
# MAGIC         "id": "q001",
# MAGIC         "question": ["Your question here"]
# MAGIC       }
# MAGIC     ]
# MAGIC   },
# MAGIC   "data_sources": {
# MAGIC     "tables": [
# MAGIC       {
# MAGIC         "identifier": "catalog.schema.your_gold_table",
# MAGIC         "description": ["One-liner about what this table contains"]
# MAGIC       }
# MAGIC     ]
# MAGIC   },
# MAGIC   "instructions": {
# MAGIC     "text_instructions": [
# MAGIC       {
# MAGIC         "id": "i001",
# MAGIC         "content": ["Your domain instructions here"]
# MAGIC       }
# MAGIC     ]
# MAGIC   }
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC Replace `catalog.schema.your_gold_table` with your own table, and fill in the instructions and questions.
# MAGIC Then deploy via `databricks bundle deploy` to make it live.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next: Notebook 6 - Build & Ship an App
# MAGIC
# MAGIC You now have:
# MAGIC - A medallion data pipeline with gold-layer tables (Notebook 4)
# MAGIC - A Genie Agent for business users to ask questions in plain English (this notebook)
# MAGIC - Genie One enabled for enterprise-wide routing
# MAGIC
# MAGIC In **Notebook 6**, you will build a **Databricks App** - a web UI that lets end users explore the same data
# MAGIC without leaving Publix's internal systems. That app will use your own gold table and can invoke Genie as a backend service.
