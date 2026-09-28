# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 4 - Build and Ship an App with Genie Code CLI
# MAGIC ### Agentic Development on Databricks - Publix Workshop
# MAGIC
# MAGIC **Goal:** take an idea to a governed, deployed Databricks App using terminal automation,
# MAGIC the way your engineers already work. ~45 minutes (mostly waiting for Genie Code).
# MAGIC
# MAGIC By now you have built real-time ingest, a medallion pipeline, and Genie agents. This lab
# MAGIC shows the last mile: app scaffolding, warehouse wiring, and deployment through your
# MAGIC Azure DevOps + DABs + service principal flow.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will build
# MAGIC
# MAGIC A **Store & Item Insights** Databricks App - a governed, SQL-backed dashboard over your
# MAGIC gold layer (`publix_agentic_workshop.medallion.gold_store_item_daily`). It will show
# MAGIC top-selling items by store, let you filter by store and date range, and run queries
# MAGIC against a SQL warehouse - not a notebook.
# MAGIC
# MAGIC Why this path:
# MAGIC - **No copy-paste.** Genie Code builds the app skeleton, API, React frontend, and database wiring.
# MAGIC - **Governed.** Everything is SQL, warehouse-backed, and audited through Unity Catalog.
# MAGIC - **Deployable.** You check it into GitHub, open a PR, and `databricks bundle deploy` ships it - matching Publix's automation.
# MAGIC - **Repeatable.** Once deployed, anyone can fork this template for their own use case.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Two paths (both get you to the same app)
# MAGIC
# MAGIC The **Genie Code CLI is in private preview**. Availability varies by workspace. Below
# MAGIC we show both:
# MAGIC
# MAGIC | Path | When to use | Effort |
# MAGIC |------|-------------|--------|
# MAGIC | **Genie Code CLI** | Terminal-first developers, local git workflow, CI/CD automation | ~10 min interactive prompting |
# MAGIC | **Genie Code UI + Agent Skills** | Faster to see results, no CLI setup, works on any workspace | ~15 min prompting in workspace |
# MAGIC
# MAGIC If the CLI is not available in your workspace, **skip to Path B (Genie Code UI)** below.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Path A: Genie Code CLI (Terminal-First)
# MAGIC
# MAGIC ### Step 1: Authenticate and install Agent Skills
# MAGIC
# MAGIC Open your terminal. If you have the Genie Code CLI binary, start here.
# MAGIC
# MAGIC ```bash
# MAGIC # Confirm CLI is installed
# MAGIC genie --version
# MAGIC
# MAGIC # Authenticate your Databricks CLI profile against the Azure workspace
# MAGIC databricks auth login \
# MAGIC   --host https://adb-<workspace-id>.centralindia.azuredatabricks.net \
# MAGIC   --profile publix-azure
# MAGIC
# MAGIC # Verify connection
# MAGIC databricks current-user me --profile publix-azure
# MAGIC
# MAGIC # Install Databricks Agent Skills (teaches Genie Code your standards)
# MAGIC databricks aitools install --scope project
# MAGIC ```
# MAGIC
# MAGIC If `genie --version` fails, **jump to Path B below** - the CLI is not available in your workspace yet.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2: Clone the repo and launch Genie Code
# MAGIC
# MAGIC ```bash
# MAGIC # Your team repo (Azure DevOps or GitHub)
# MAGIC git clone https://your-azure-devops.com/publix/stores-analytics
# MAGIC cd stores-analytics
# MAGIC
# MAGIC # Create a feature branch
# MAGIC git checkout -b feature/store-item-insights-app
# MAGIC
# MAGIC # Launch Genie Code CLI
# MAGIC genie
# MAGIC ```
# MAGIC
# MAGIC On first launch, Genie Code will ask which CLI profile to use. Select `publix-azure`.
# MAGIC
# MAGIC You are now in an interactive agent loop. Every prompt you type goes to Genie Code;
# MAGIC it sees your local files, terminal, and Databricks workspace.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3: Scaffold the app
# MAGIC
# MAGIC Inside the `genie` prompt, paste this:
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Create a new Databricks App named "store-item-insights" at ./apps/store-item-insights/.
# MAGIC > It should be a Node.js/React app with a FastAPI Python backend.
# MAGIC > The backend will query publix_agentic_workshop.medallion.gold_store_item_daily
# MAGIC > via a SQL warehouse.
# MAGIC >
# MAGIC > Files to create:
# MAGIC > - app.yaml with basic config and default mode "snapshot"
# MAGIC > - databricks.yml (bundle manifest) with warehouse_id and catalog refs
# MAGIC > - backend/ with a FastAPI server that lists stores and top items
# MAGIC > - frontend/ with React components for store filter, date range picker, and a table of top items
# MAGIC >
# MAGIC > Use this catalog: publix_agentic_workshop.medallion.gold_store_item_daily
# MAGIC > Warehouse: publix-workshop-wh
# MAGIC >
# MAGIC > Structure it so it can be deployed with "databricks bundle deploy".
# MAGIC > ```
# MAGIC
# MAGIC Genie Code will generate the skeleton, create all the files, and show you a plan.
# MAGIC **Read the plan carefully** - this is your chance to catch anything off. Then approve to write the files.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 4: Wire it to the warehouse and add a useful query
# MAGIC
# MAGIC Still inside `genie`:
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Update the FastAPI backend to add a new route /api/top-items that:
# MAGIC > - Takes query params: store_id (string), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)
# MAGIC > - Queries publix_agentic_workshop.medallion.gold_store_item_daily
# MAGIC > - Returns the top 20 items by revenue in JSON: [{item_id, item_name, store_id, revenue, units_sold}, ...]
# MAGIC > - Handles empty result sets gracefully
# MAGIC > - Logs the query to Databricks system tables so we can audit data access
# MAGIC >
# MAGIC > Update the React frontend to call this endpoint and display results in a table with
# MAGIC > sortable columns and a loading state.
# MAGIC > ```
# MAGIC
# MAGIC Approve Genie Code's changes. It will add the query, update the backend routes, and
# MAGIC wire the frontend components.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 5: Test locally and ship it
# MAGIC
# MAGIC Still inside `genie`:
# MAGIC
# MAGIC > **🧞 Prompt for Genie Code**
# MAGIC > ```
# MAGIC > Test the app locally:
# MAGIC > 1. Start the FastAPI backend with "python -m uvicorn backend.main:app --reload"
# MAGIC > 2. In another terminal, start the React dev server: "npm run dev" in frontend/
# MAGIC > 3. Open http://localhost:3000 and verify the store filter and top-items table load
# MAGIC > 4. Try a few filter combinations - stores, date ranges
# MAGIC > 5. Check that queries run against the SQL warehouse
# MAGIC >
# MAGIC > Then:
# MAGIC > 1. Commit all changes to the feature branch
# MAGIC > 2. Create a pull request with title "Add Store & Item Insights app"
# MAGIC > 3. Include the app description, screenshots if possible, and the warehouse queries
# MAGIC > ```
# MAGIC
# MAGIC Genie Code will run the tests, open the PR against your repo, and show you the link.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 6: Deploy with Databricks Asset Bundles
# MAGIC
# MAGIC Once your PR is approved:
# MAGIC
# MAGIC ```bash
# MAGIC # Switch to main and pull the merged code
# MAGIC git checkout main
# MAGIC git pull
# MAGIC
# MAGIC # Validate the bundle
# MAGIC databricks bundle validate
# MAGIC
# MAGIC # Deploy to your workspace (uses the service principal from your Azure DevOps context)
# MAGIC databricks bundle deploy
# MAGIC
# MAGIC # Start the app
# MAGIC databricks bundle run store-item-insights
# MAGIC
# MAGIC # The app is now live. Get the URL:
# MAGIC databricks apps get store-item-insights
# MAGIC ```
# MAGIC
# MAGIC Nothing goes to production outside automation. All deployments are audited through
# MAGIC your Databricks workspace Activity Log.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Path B: Genie Code UI + Agent Skills (If CLI Not Available)
# MAGIC
# MAGIC If `genie --version` failed or you prefer the workspace UI:
# MAGIC
# MAGIC 1. **Install Agent Skills** (one-time):
# MAGIC    Open a terminal and run:
# MAGIC    ```bash
# MAGIC    databricks aitools install --scope workspace
# MAGIC    ```
# MAGIC
# MAGIC 2. **Open Genie Code in this workspace** (click the sparkle icon at top right of this notebook, or press `Cmd/Ctrl + I`).
# MAGIC
# MAGIC 3. **Use the same prompts from Path A**, pasted into the Genie Code panel.
# MAGIC
# MAGIC 4. **Create the app files in your workspace**, then:
# MAGIC    ```bash
# MAGIC    # Download the generated files to your local repo
# MAGIC    git clone your-repo
# MAGIC    # Copy app files from workspace to local
# MAGIC    databricks workspace export-dir /Users/your-email/store-item-insights ./apps/
# MAGIC    # Commit and PR as above
# MAGIC    ```
# MAGIC
# MAGIC The result is identical - you get the same deployed app, same way.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Keep a human in the loop
# MAGIC
# MAGIC Every time Genie Code generates a plan (before it writes files):
# MAGIC
# MAGIC - **Read the changes.** Skim the backend routes, the warehouse queries, the React components.
# MAGIC - **Ask questions.** "Why are you using that column?" "Can we add caching?" "Does this need error handling?"
# MAGIC - **Reject or iterate.** If something looks wrong, say so - Genie Code will refactor and try again.
# MAGIC - **Approve to write.** Only then does Genie Code touch the filesystem.
# MAGIC
# MAGIC **You stay in control.** Genie Code is a pair programmer, not an autopilot.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What just happened
# MAGIC
# MAGIC You took a description ("I want an app that shows top items by store") and:
# MAGIC
# MAGIC 1. Generated app scaffolding + backend + frontend
# MAGIC 2. Wired it to your SQL warehouse
# MAGIC 3. Tested it locally
# MAGIC 4. Opened a PR for review
# MAGIC 5. Deployed it through Databricks Asset Bundles
# MAGIC
# MAGIC This is the same path the **Vibe-to-Value app** took. Once deployed, any analyst at
# MAGIC Publix can:
# MAGIC - Modify the SQL queries in the backend
# MAGIC - Fork the template for new use cases (cost per store, inventory by aisle, etc.)
# MAGIC - Deploy new versions through the same pipeline
# MAGIC
# MAGIC **No copy-paste. No manual clicking. No bottleneck.** Just prompts, PRs, and bundles.
# COMMAND ----------

# MAGIC %md
# MAGIC ## Next steps
# MAGIC
# MAGIC - **Your app is live** - share the URL with stakeholders
# MAGIC - **Iterate** - use Genie Code to add filters, new metrics, or export features
# MAGIC - **Teach others** - this template now exists in your repo for the next analyst
# MAGIC - **Scale** - every new dashboard, agent, or pipeline follows the same pattern
