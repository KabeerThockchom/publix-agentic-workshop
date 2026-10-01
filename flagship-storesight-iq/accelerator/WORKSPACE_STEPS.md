# Workspace Steps — deploy + wire the app

The whole deploy is four commands. Almost everything that used to be a manual
"click in the workspace UI" step is now automated by `accelerator/wire_app.py`.
This doc lists (1) the few genuine prerequisites a person sets up once, (2) the
four-command deploy, and (3) an appendix with the raw SQL/CLI the script runs —
for when you want to understand it, run a step by hand, or debug a failure.

> ⛔ **ISOLATION — deploy each customer from a SEPARATE working directory** (fresh
> `git clone`/`git worktree`). Each customer already gets a unique `bundle.name`
> and a unique DAB **target** (both = `<short_code>`), but the local Terraform
> state cache `.databricks/bundle/<target>/` lives in the working dir — sharing a
> dir across customers risks the 2nd deploy reconciling and DELETING the 1st's
> schema/app/jobs (it happened twice). Before `bundle deploy`, confirm
> `databricks bundle summary` + `.databricks/bundle/<target>/terraform/terraform.tfstate`
> list ONLY this customer. **Never `--auto-approve` a deploy that reports deleting a
> schema/app/job.**

```bash
python accelerator/generate.py                                   # apply the two config files
databricks bundle deploy -p <profile>                     # schema + setup job + app shell
databricks bundle run    storesight_setup -p <profile>    # notebooks 01→07: data · ML · serving · genie · streaming
python accelerator/wire_app.py                                   # wire everything into the app (no UI)
```

> ⚠️ **Never `databricks bundle deploy` after `wire_app.py`.** `bundle deploy`
> reconciles the app to exactly the resources declared in `databricks.yml` (only
> the SQL warehouse) and **wipes** the serving endpoints / secret / Lakebase that
> the wiring script attached. If you must redeploy the bundle, re-run
> `wire_app.py` afterwards.

---

## 1. Prerequisites (a person does these once, before deploying)

These are the only genuinely manual pieces — mostly because they predate the app
or need workspace-admin rights.

- [ ] **Unity Catalog `<catalog>` exists.** The accelerator does NOT run
      `CREATE CATALOG` (it fails when account default storage is off). Create it,
      or point `customer_config.yaml` at an existing catalog.
- [ ] **A SQL Warehouse exists.** Put its id in `customer_config.yaml`
      (`databricks.sql_warehouse_id`). Serverless is fine.
- [ ] **A CLI profile for the target workspace** is in `~/.databrickscfg`
      (`databricks auth profiles`), named in `customer_config.yaml`
      (`databricks.profile`). Everything targets this profile/workspace.
- [ ] **A project-based Lakebase instance** named `<resource_prefix>-oltp` exists
      (create it in the workspace; the app authenticates with the caller's OAuth
      token as the Postgres password, so no secret is needed).
- [ ] **Workspace-admin** for the caller (or a one-time admin pass) — only needed
      for the external-embedding toggle in step 7 of the wiring script; if the
      caller isn't an admin, that single step is the one manual fallback (see the
      appendix). Everything else works with normal user rights.
- [ ] **(Optional) Ticketmaster events:** if you want the local-events demand
      signal, create the secret and set `external_apis.ticketmaster_secret` in
      `customer_config.yaml` (see the appendix). With no key the app degrades
      gracefully — events enrichment just returns empty.
- [ ] **(Optional) Customer logo:** drop the logo files in `accelerator/assets/`
      and point `customer_config.yaml` at them (`generate.py` wires them into the
      frontend + favicons).

## 2. Deploy + run the setup

```bash
databricks bundle deploy -p <profile>
databricks bundle run   storesight_setup -p <profile>
```

The job runs notebooks 01→07: schema + synthetic data + the 4 materialized views
(`mv_daily_sales`, `mv_employees`, `mv_inventory`, `mv_store_overview`), 4 trained
+ served models, the Genie space (pointed at the MVs), and the streaming job.
Serving endpoints reach READY at the end.

## 3. Wire the app (automated — no UI)

```bash
python accelerator/wire_app.py            # add --dry-run first to preview every action
```

This performs, idempotently, everything that used to be manual:

| Step | What it does | Why it can't be in the DAB |
|---|---|---|
| Discover | app SP, Lakebase DNS, Genie space id, current user | — |
| UC grants | `USE_CATALOG` / `USE_SCHEMA` / `SELECT` to the app SP | SP only exists after first app deploy |
| Lakebase grant | `SET ROLE pg_database_owner; GRANT USAGE, CREATE ON SCHEMA public …` | Postgres is a separate permission system from UC |
| Attach resources | 4 serving endpoints (+CAN_QUERY), secret (+READ), Lakebase (+CAN_CONNECT_AND_CREATE) | endpoints don't exist at first `bundle deploy` |
| Genie env | writes `GENIE_SPACE_ID` into `app.yaml` | space id only known after the setup job |
| Warm endpoints | `scale_to_zero=false` for responsive demos | post-serving tuning |
| Embedding | `aibi-dashboard-embedding-access-policy = ALLOW_ALL_DOMAINS` | admin setting |
| Deploy | `apps start` → `apps deploy` → poll `/api/health` | must run after resources are attached |

Run `python accelerator/wire_app.py --dry-run` first to see every CLI call
without executing. Use `--no-warm` to leave endpoints scale-to-zero (cheaper).

## 4. Verify

```bash
curl -s https://<app-url>/api/health   # expect "healthy" — warehouse + Lakebase + genie all configured
```

`wire_app.py` already polls `/api/health` at the end. Then open the app:
Login → Store Operations (live data) · Forecast/Labor/Inventory/Prep (ML) ·
Regional Map (3D fleet) · Compare (embedded Genie).

## 5. Teardown (rebuild from zero / clean up)

```bash
databricks bundle run     storesight_teardown -p <profile>   # setup/teardown.py
databricks bundle destroy -p <profile> --auto-approve
```

The `storesight_teardown` job runs `setup/teardown.py`, which idempotently removes
everything setup created that the bundle doesn't own (the 4 serving endpoints, the
streaming job + its simulator notebook, the Genie space, and the UC schema via
`DROP SCHEMA … CASCADE`). `bundle destroy` then removes the bundle-managed
resources (setup job, teardown job, app, empty schema resource). The catalog and
Lakebase instance are left in place (prerequisites you own). A clean workspace can
run setup → teardown → setup and end working — see `setup/README.md`.

---

## Appendix — the raw steps (for debugging or manual runs)

`wire_app.py` runs exactly these. Swap in your values from `customer_config.yaml`
(`<catalog>`, `<schema>`, `<app-sp>`, `<resource_prefix>`, …).

### A. UC grant to the app service principal
Find the SP: `databricks apps get <app_name> -p <profile>` →
`service_principal_client_id`. Then:
```sql
GRANT USE CATALOG ON CATALOG `<catalog>` TO `<app-sp>`;
GRANT USE SCHEMA, SELECT ON SCHEMA `<catalog>`.`<schema>` TO `<app-sp>`;
```

### B. Lakebase Postgres grant
UC grants do **not** cover Postgres, and the `database` app-resource's
`CAN_CONNECT_AND_CREATE` does **not** confer `CREATE` on the `public` schema:
on PG16 `public` is owned by `pg_database_owner`, and a plain `GRANT` by the
deploying user only confers `USAGE` (they hold `CREATE` without grant-option). So
you must assume the owner role first. Connect to `databricks_postgres` (OAuth
token as the password) and run these as **two separate statements** (wire_app.py
does the same):

```sql
-- (1) CRITICAL — as pg_database_owner (which owns `public`). Run on its own so a
--     later error can't roll it back. This is all a FRESH deploy needs: the app
--     then creates its own tables (owned by the app SP) and can read/write them.
SET ROLE pg_database_owner;
GRANT USAGE, CREATE ON SCHEMA public TO "<app-sp>";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "<app-sp>";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO "<app-sp>";
```
```sql
-- (2) BEST-EFFORT — only when REUSING a Lakebase whose tables already exist from a
--     prior deploy (a restore). Run AS THE CONNECTING USER (do NOT `SET ROLE`),
--     because only a table's owner can GRANT on it and those tables are owned by
--     the deploying user, not pg_database_owner. Non-fatal; safe to re-run (it
--     self-heals the app SP's write grants, which a database-resource re-attach
--     resets). A fresh Lakebase has no such tables, so this is a harmless no-op.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "<app-sp>";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "<app-sp>";
```
Without `CREATE` (step 1), the app's `_ensure_tables()` fails at startup with
`permission denied for schema public`. Without step 2 on a **reused** Lakebase,
the app connects but inventory/prep submissions silently fail to persist.

### C. Attach app resources
```bash
databricks apps create-update <app_name> -p <profile> --json '{
  "update_mask": "resources",
  "app": { "resources": [
    {"name":"sql_warehouse","sql_warehouse":{"id":"<warehouse_id>","permission":"CAN_USE"}},
    {"name":"demand_forecast","serving_endpoint":{"name":"<prefix>-demand-forecast","permission":"CAN_QUERY"}},
    {"name":"labor_optimizer","serving_endpoint":{"name":"<prefix>-labor-optimizer","permission":"CAN_QUERY"}},
    {"name":"inventory_predictor","serving_endpoint":{"name":"<prefix>-inventory-predictor","permission":"CAN_QUERY"}},
    {"name":"prep_scheduler","serving_endpoint":{"name":"<prefix>-prep-scheduler","permission":"CAN_QUERY"}},
    {"name":"lakebase","database":{"instance_name":"<prefix>-oltp","database_name":"databricks_postgres","permission":"CAN_CONNECT_AND_CREATE"}}
  ]}
}'
```
Attaching a serving-endpoint / secret / database resource auto-grants the app SP
the stated permission. `create-update` with `update_mask=resources` replaces the
resource set, so include the warehouse too.

### D. Genie env
Set `GENIE_SPACE_ID` in `app.yaml` to the id printed by notebook 06
(`databricks genie list-spaces -p <profile>` → match on the space title).

### E. External embedding (needs workspace-admin)
```bash
databricks settings aibi-dashboard-embedding-access-policy update -p <profile> --json '{
  "allow_missing": true,
  "field_mask": "aibi_dashboard_embedding_access_policy.access_policy_type",
  "setting": {"aibi_dashboard_embedding_access_policy":{"access_policy_type":"ALLOW_ALL_DOMAINS"},"setting_name":"default"}
}'
```
Without it the Compare page's Genie iframe is blocked; the rest of the app is
unaffected.

### F. Start + deploy the app
```bash
databricks apps start  <app_name> -p <profile>
databricks apps deploy <app_name> -p <profile> \
  --source-code-path /Workspace/Users/<you>/.bundle/storesight-iq-<short_code>/files
```

### G. (Optional) Ticketmaster secret
```bash
databricks secrets create-scope <scope> -p <profile>
databricks secrets put-secret  <scope> <key> -p <profile>   # paste your Consumer Key
```
Set `external_apis.ticketmaster_secret: "<scope>/<key>"` in `customer_config.yaml`;
`generate.py` activates the `TICKETMASTER_API_KEY` env (`valueFrom: ticketmaster_secret`)
and `wire_app.py` attaches the matching secret app-resource. Never commit a literal
key. Get a free one at https://developer.ticketmaster.com/explore/ ("Get Your API
Key"). With the guided skill this is collected DURING the interview and the secret
is created before deploy — this appendix is the by-hand equivalent.
