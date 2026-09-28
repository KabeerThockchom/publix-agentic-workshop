# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 0 - Setup & Orientation
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** get oriented, meet Genie Code, and confirm your environment works. ~15 minutes.
# MAGIC
# MAGIC By the end of the day you will have built, with Genie Code, a real-time ingest, a
# MAGIC medallion pipeline, a Genie space, and an app - on data that looks like yours. This
# MAGIC notebook is the on-ramp.

# COMMAND ----------

# MAGIC %md
# MAGIC ## How this workshop works
# MAGIC
# MAGIC You will not copy-paste finished code. You will **describe what you want** and let
# MAGIC Genie Code build it, then review and deploy. That is the loop, every time:
# MAGIC
# MAGIC | Step | What you do | What Genie Code does |
# MAGIC |------|-------------|----------------------|
# MAGIC | **Describe** | Say what you want in plain language | - |
# MAGIC | **Generate** | - | Writes the code + a plan, with Unity Catalog context |
# MAGIC | **Review** | Read the plan, open a PR, keep a human in the loop | - |
# MAGIC | **Deploy** | Ship it | Runs it, governed by Unity Catalog |
# MAGIC
# MAGIC Each lab gives you a **Genie Code prompt** to start from. Change it, break it, make it
# MAGIC yours. A **reference solution** is included in case you want to compare - but the point
# MAGIC is the prompting, not the paste.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Where to type the prompts
# MAGIC
# MAGIC Two surfaces, same engine - use whichever you like:
# MAGIC
# MAGIC - **Genie Code in the workspace** - the assistant panel in this notebook (sparkle icon,
# MAGIC   or `Cmd/Ctrl + I`). Best for building right here.
# MAGIC - **Genie Code CLI** - in your terminal, against your local repo. Best if your GitHub is
# MAGIC   already set up locally. We cover this in Lab 4.
# MAGIC
# MAGIC Look for the **🧞 Prompt for Genie Code** blocks. That is your cue to stop reading and
# MAGIC start prompting.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Your environment
# MAGIC
# MAGIC Everything today lives in one Unity Catalog catalog. Confirm you can see it below.
# MAGIC
# MAGIC | Resource | Value |
# MAGIC |----------|-------|
# MAGIC | Catalog | `publix_agentic_workshop` |
# MAGIC | Schemas | `bronze` (raw ingest), `medallion` (silver + gold) |
# MAGIC | SQL warehouse | `publix-workshop-wh` |
# MAGIC | LLM endpoint | `databricks-claude-opus-4-8` |

# COMMAND ----------

# confirm the catalog + schemas are visible
spark.sql("SHOW SCHEMAS IN publix_agentic_workshop").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Warm-up: your first Genie Code prompt
# MAGIC
# MAGIC Let's make sure prompting works. Open Genie Code and try this.
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Show me the tables in the publix_agentic_workshop.bronze schema, and for
# MAGIC > sales_events give me the row count and 5 sample rows.
# MAGIC > ```
# MAGIC
# MAGIC Genie Code should write and run SQL against the catalog. If you get rows back, you are
# MAGIC ready. If the bronze tables are empty, that is expected - you will fill them in Lab 1.

# COMMAND ----------

# reference solution (what Genie Code should produce)
spark.sql("SELECT count(*) AS rows FROM publix_agentic_workshop.bronze.sales_events").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Teach Genie Code your standards (optional, powerful)
# MAGIC
# MAGIC The real unlock: Genie Code can follow **your** conventions if you give it context. Two
# MAGIC ways, both covered as we go:
# MAGIC
# MAGIC - **An instructions file** (an `AGENTS.md` / assistant instructions) that says how Publix
# MAGIC   tags data, names tables, and structures pipelines. Genie Code reads it and every
# MAGIC   generation follows it.
# MAGIC - **Agent Skills** - reusable, versioned skills (for example, your homegrown ETL
# MAGIC   framework) that Genie Code invokes so generated code uses your framework, not a
# MAGIC   generic one.
# MAGIC
# MAGIC Keep this in mind: anywhere you would say "but at Publix we do it this way," that is a
# MAGIC candidate for an instruction or a skill.

# COMMAND ----------

# MAGIC %md
# MAGIC ## You're set. Next up:
# MAGIC
# MAGIC 1. **Lab 1** - Real-time ingest with Zerobus
# MAGIC 2. **Lab 2** - Medallion pipeline with Spark Declarative Pipelines
# MAGIC 3. **Lab 3** - Ask your data with Genie spaces + Genie One
# MAGIC 4. **Lab 4** - Build and ship an app with the Genie Code CLI
# MAGIC
# MAGIC Then the Vibe-to-Value app, so anyone at Publix can self-serve after today.
