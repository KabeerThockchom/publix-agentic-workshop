# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 3 - Ask Your Data with Genie Spaces + Genie One
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** build a curated Genie space so business users can ask questions in plain English. No SQL knowledge required. ~45 minutes.
# MAGIC
# MAGIC By now you have gold-layer data (Lab 2). This lab makes it self-serve: you will build a Genie space on
# MAGIC `publix_agentic_workshop.medallion.gold_store_item_daily`, add example questions, and enable Genie One
# MAGIC so users can route questions across multiple spaces. Then anyone at Publix can ask "what drove revenue last week?" and get an answer.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What is a Genie Space?
# MAGIC
# MAGIC A **Genie space** (now called Genie Agent in latest docs) is a curated front door to your data.
# MAGIC It sits between your tables and business users and includes:
# MAGIC
# MAGIC - **Tables** - the gold semantic layer tables Genie can query
# MAGIC - **General instructions** - domain guidance (what revenue means, how to interpret time ranges, vocabulary)
# MAGIC - **Certified example questions** - seed the search with real, correct examples + their SQL
# MAGIC - **Metrics/SQL expressions** - reusable calculations (total_revenue, avg_units_per_line)
# MAGIC
# MAGIC When a user types a question, Genie:
# MAGIC 1. Reads your instructions
# MAGIC 2. Searches the example questions for relevance
# MAGIC 3. Generates SQL against your tables
# MAGIC 4. Runs the query and returns results
# MAGIC
# MAGIC You control what tables are visible and what SQL patterns Genie learns from the examples.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The Gold Layer You Built
# MAGIC
# MAGIC Your data is ready. Confirm the table exists and has data:

# COMMAND ----------

spark.sql("""
SELECT count(*) as row_count, min(sales_date) as oldest_date, max(sales_date) as newest_date
FROM publix_agentic_workshop.medallion.gold_store_item_daily
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC And a sample row, so you see the shape:

# COMMAND ----------

spark.sql("""
SELECT * FROM publix_agentic_workshop.medallion.gold_store_item_daily
LIMIT 5
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Important: API Limitation on This Workspace
# MAGIC
# MAGIC The Genie space **create/update API is currently unreliable** on this FEVM workspace. So instead of
# MAGIC having you script the space creation, we will:
# MAGIC
# MAGIC 1. Use the **Genie Code prompts below** to DRAFT the space's instructions, example questions, and metrics
# MAGIC 2. PASTE those drafts into the Genie UI in your workspace
# MAGIC 3. Test the space by typing natural-language questions
# MAGIC
# MAGIC This is not a limitation of Genie Code - it is a limitation of the lab environment. In production,
# MAGIC Genie spaces are typically defined in code (`.geniespace.json`) and deployed via Declarative Automation Bundles.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create the Space in the UI
# MAGIC
# MAGIC In your Databricks workspace, open **Genie** (left sidebar icon) → **Spaces** → **New Space**.
# MAGIC
# MAGIC | Field | Value |
# MAGIC |-------|-------|
# MAGIC | **Name** | `Publix Store & Item Sales` |
# MAGIC | **Description** | `Ask questions about store and item sales performance, revenue, and trends.` |
# MAGIC | **Warehouse** | `publix-workshop-wh` (or the SQL warehouse you have access to) |
# MAGIC
# MAGIC Click **Create**. You now have an empty space. Keep it open - we will add tables and instructions next.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Add the Gold Table
# MAGIC
# MAGIC In the space settings:
# MAGIC
# MAGIC 1. **Data sources** → **Add tables**
# MAGIC 2. Search for `publix_agentic_workshop.medallion.gold_store_item_daily`
# MAGIC 3. Click to add it
# MAGIC 4. In the table row, click the **description icon** and add a one-liner:
# MAGIC    ```
# MAGIC    Daily sales aggregated by store and item (units sold, revenue, line items).
# MAGIC    ```
# MAGIC 5. **Save**
# MAGIC
# MAGIC Genie now knows which columns are available and can use them in queries.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Add General Instructions
# MAGIC
# MAGIC This tells Genie how to interpret user questions. Open Genie Code and run this prompt:
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > I'm building a Genie space for grocery retail business users at Publix.
# MAGIC > They will ask about store and item sales.
# MAGIC >
# MAGIC > The table is publix_agentic_workshop.medallion.gold_store_item_daily with these columns:
# MAGIC > - store_number: unique store ID
# MAGIC > - item_id: unique SKU
# MAGIC > - item_name: product name
# MAGIC > - item_category: product category (produce, deli, grocery, etc.)
# MAGIC > - sales_date: date of the sales (DATE type)
# MAGIC > - units_sold: quantity sold
# MAGIC > - revenue: total sales in dollars
# MAGIC > - line_items: count of unique transaction lines
# MAGIC >
# MAGIC > Generate comprehensive general instructions for the space. Include:
# MAGIC > - Domain context (grocery retail, daily aggregates)
# MAGIC > - What revenue, units_sold, and line_items mean
# MAGIC > - How to interpret time ranges (last week, last month, Q1, etc.)
# MAGIC > - Publix-specific vocabulary (deli, produce, meat, etc.)
# MAGIC > - Any gotchas (e.g., dates are UTC, missing sales days may be 0)
# MAGIC >
# MAGIC > Format as markdown. Be concise but complete (150-200 words).
# MAGIC > ```
# MAGIC
# MAGIC Copy the instructions Genie generates, then paste them in the Genie UI:
# MAGIC - In your space → **Settings** → **General instructions**
# MAGIC - Paste the block
# MAGIC - **Save**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Add Certified Example Questions
# MAGIC
# MAGIC Example questions teach Genie what kinds of questions to expect and lock in correct SQL patterns.
# MAGIC Use this prompt to generate 8 strong examples:
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Generate 8 certified example questions for a Genie space on Publix store & item sales.
# MAGIC >
# MAGIC > Table: publix_agentic_workshop.medallion.gold_store_item_daily
# MAGIC > Columns: store_number, item_id, item_name, item_category, sales_date, units_sold, revenue, line_items
# MAGIC >
# MAGIC > Include a variety:
# MAGIC > 1. Top items by revenue (e.g., "What were the top 10 items by revenue last month?")
# MAGIC > 2. Revenue by store (e.g., "Which store generated the most revenue in the last 7 days?")
# MAGIC > 3. Category trends (e.g., "How did produce revenue trend week-over-week in September?")
# MAGIC > 4. Daily pattern (e.g., "What is the average daily revenue per store?")
# MAGIC > 5. Customer behavior (via line_items; e.g., "Which stores have the most line items per transaction?")
# MAGIC > 6. Item performance (e.g., "Show me items with declining units sold month-over-month")
# MAGIC > 7. Store comparison (e.g., "Compare the top 5 stores by revenue and units sold")
# MAGIC > 8. Anomaly (e.g., "Which items had zero revenue yesterday but sold last week?")
# MAGIC >
# MAGIC > For each question, provide:
# MAGIC > - The plain-English question
# MAGIC > - The exact SQL (using 3-level namespace, uppercase keywords, lowercase identifiers)
# MAGIC > - A one-line description
# MAGIC >
# MAGIC > Use realistic dates (assume today is the current date). Format as a table.
# MAGIC > ```
# MAGIC
# MAGIC For each example question:
# MAGIC 1. In the Genie UI → **Settings** → **Example questions**
# MAGIC 2. Click **Add example question**
# MAGIC 3. Paste the question text
# MAGIC 4. Paste the SQL in the "Sample SQL" field
# MAGIC 5. **Save**
# MAGIC
# MAGIC (If the UI offers a bulk-import option, use it instead - faster.)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: (Optional) Add SQL Expressions for Metrics
# MAGIC
# MAGIC If your space supports **metric definitions**, you can add reusable SQL blocks. Run this prompt:
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Generate 2-3 SQL expressions (metric definitions) for a Genie space on grocery retail sales.
# MAGIC > Table: publix_agentic_workshop.medallion.gold_store_item_daily
# MAGIC >
# MAGIC > Include:
# MAGIC > 1. total_revenue: sum of all revenue in the result set
# MAGIC > 2. avg_units_per_item: average units_sold per unique item
# MAGIC > 3. conversion_rate: line_items / units_sold (as a percentage)
# MAGIC >
# MAGIC > For each, provide the metric name, a one-line description, and the SQL expression (not a full query,
# MAGIC > just the calculation).
# MAGIC > ```
# MAGIC
# MAGIC Add these in the Genie UI if the **Settings** tab has a **Metrics** or **SQL Expressions** section.
# MAGIC Some spaces do not expose this; skip if not present.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Test Your Space
# MAGIC
# MAGIC Now your space is ready. In the Genie UI, open your space and type these test questions
# MAGIC in the chat box. Genie should return results within seconds.
# MAGIC
# MAGIC 1. **"What were the top 5 items by revenue last week?"**
# MAGIC    - Expect: a table with item names, categories, and revenue
# MAGIC 2. **"Show me daily revenue by store for September."**
# MAGIC    - Expect: a bar chart or table with stores and dates
# MAGIC 3. **"How did produce revenue trend from week 1 to week 2 of September?"**
# MAGIC    - Expect: a comparison showing week-over-week change
# MAGIC 4. **"Which store has the most transactions (line items)?"**
# MAGIC    - Expect: a store with high line_items count
# MAGIC 5. **"What is the average revenue per store?"**
# MAGIC    - Expect: a single number or a list with averages
# MAGIC
# MAGIC If Genie struggles with a question, it means the example questions or instructions need refinement.
# MAGIC Go back to the prompts above, ask Genie Code to improve them, and update the space.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What is Genie One?
# MAGIC
# MAGIC **Genie One** is the enterprise front door for natural-language questions **across your entire workspace**.
# MAGIC It routes questions to relevant Genie spaces, or falls back to dashboards, queries, and metric views.
# MAGIC
# MAGIC Think of it as a unified search + ask interface:
# MAGIC - User types: "What drove revenue last week?"
# MAGIC - Genie One searches and routes to the most relevant space (e.g., your "Publix Store & Item Sales" space)
# MAGIC - That space answers the question using its curated tables and instructions
# MAGIC
# MAGIC **Key facts:**
# MAGIC - **Genie One is GA** (no preview needed)
# MAGIC - Requires Consumer or higher entitlement + SQL warehouse access
# MAGIC - Routes to **one** relevant space (not all spaces; not a fan-out)
# MAGIC - Non-deterministic - relevance is based on your instructions and example questions
# MAGIC
# MAGIC For tightly controlled multi-agent scenarios, you would build multiple spaces and use an
# MAGIC orchestration layer (not Genie One). But for democratization - letting anyone self-serve - Genie One
# MAGIC is your tool.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Enable Your Space in Genie One
# MAGIC
# MAGIC Once you have created and tested your space:
# MAGIC
# MAGIC 1. In the Genie UI → your space → **Sharing & Access**
# MAGIC 2. Make sure the space is **Shared** with the teams or groups who need it
# MAGIC 3. That's it. Genie One automatically discovers shared spaces and routes to them.
# MAGIC
# MAGIC To test Genie One:
# MAGIC - Open the **Chat** interface in your workspace (top right, Chat icon)
# MAGIC - Ask: "What were our top-selling items last week?"
# MAGIC - Genie One should route to your "Publix Store & Item Sales" space and return results
# MAGIC
# MAGIC If it routes to the wrong space or no space, check:
# MAGIC - The space is shared with you
# MAGIC - The space has example questions and instructions (helps Genie One route correctly)
# MAGIC - Your warehouse is active and you have `CAN USE` permission

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next Steps: Lab 4
# MAGIC
# MAGIC You now have:
# MAGIC - A medallion data pipeline with gold-layer tables
# MAGIC - A Genie space for business users to ask questions in plain English
# MAGIC - Genie One enabled so questions route across your spaces
# MAGIC
# MAGIC In **Lab 4**, you will build a **Databricks App** - a web interface that embeds your data
# MAGIC and lets end users explore without leaving Publix's internal systems. That app will use the same
# MAGIC gold-layer tables and can invoke Genie as a backend.
# MAGIC
# MAGIC Then everyone at Publix can self-serve: ask Genie or use the app.
