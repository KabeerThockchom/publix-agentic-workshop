# Setup & Teardown

This demo is built and destroyed entirely from code — a clean workspace can run
**setup → teardown → setup** and end in a working state, with no manual steps
beyond the one-time prerequisites.

> ⛔ **One customer per bundle.** `generate.py` namespaces the DAB bundle
> (`storesight-iq-<short_code>`) and its default target (`<short_code>`) from the
> customer's `short_code`, so setup/teardown always act on **that** customer's
> resources — no `-t` flag needed. Give each customer a globally unique
> `short_code` and deploy each from its own working directory (clone/worktree), or
> a second customer's deploy can overwrite the first's. See
> `../accelerator/WORKSPACE_STEPS.md`.

## Prerequisites (owned by you, reused across rebuilds — not created/destroyed)
- A Unity Catalog **catalog** (the setup does not `CREATE CATALOG`).
- A **SQL warehouse** (id in `accelerator/customer_config.yaml`).
- A project-based **Lakebase instance** (`<resource_prefix>-oltp`).
- A **CLI profile** for the target workspace.

See `../accelerator/WORKSPACE_STEPS.md` §1 for details.

## Setup (idempotent — safe to re-run)

```bash
python accelerator/generate.py                            # apply the config (idempotent)
databricks bundle deploy   -p <profile>                   # schema + setup job + app
databricks bundle run      storesight_setup -p <profile>  # notebooks 01→07
python accelerator/wire_app.py                            # wire the app (profile read from config; no -p)
```

Every setup step is safe to re-run: tables are written with `mode("overwrite")`,
views use `CREATE OR REPLACE`, materialized views `DROP … IF EXISTS` + recreate,
the serving endpoints get-or-update, the Genie space + streaming job are
create-or-reuse, and the generator is idempotent.

> ⚠️ Don't `bundle deploy` again after `wire_app.py` — it reconciles the app to the
> resources declared in `databricks.yml` and wipes the endpoints/secret/Lakebase the
> script attached. Re-run `wire_app.py` if you must redeploy the bundle.

## Teardown (idempotent — removes everything setup created)

```bash
databricks bundle run     storesight_teardown -p <profile>   # setup/teardown.py
databricks bundle destroy -p <profile> --auto-approve        # removes THIS customer's bundle
```

- **`setup/teardown.py`** (run by the `storesight_teardown` job) removes the
  resources the bundle doesn't own, all guarded with `IF EXISTS` / ignore-missing:
  the 4 serving endpoints, the streaming job + its generated simulator notebook,
  the Genie space, and the Unity Catalog schema (`DROP SCHEMA … CASCADE` → tables,
  views, materialized views, registered models).
- **`bundle destroy`** removes the bundle-managed resources: the setup job, the
  teardown job, the app, and the now-empty schema resource. It's scoped to this
  customer's namespaced bundle — safe to `--auto-approve` here (unlike a *deploy*
  reconcile) because you are explicitly tearing this customer down. Just confirm
  you're in the intended customer's working directory first.

The catalog and the Lakebase instance are left in place (prerequisites you own).

## Verify a full cycle

```bash
# from a clean workspace:
databricks bundle deploy -p <profile> && \
databricks bundle run storesight_setup -p <profile> && \
python accelerator/wire_app.py                          # → working demo

databricks bundle run storesight_teardown -p <profile> && \
databricks bundle destroy -p <profile> --auto-approve   # → clean workspace

# then repeat the setup block → the demo rebuilds identically.
```

Re-running teardown on an already-clean workspace is a no-op (every delete is
guarded), so the cycle is fully repeatable.
