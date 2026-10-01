#!/usr/bin/env python3
"""
wire_app.py — automated post-deploy wiring for the StoreSight IQ QSR accelerator.

This runs EVERYTHING that used to be a manual "workspace step" in
accelerator/WORKSPACE_STEPS.md — end to end, no UI clicks. Run it once after
`databricks bundle deploy` + `databricks bundle run storesight_setup` have
finished (the setup job creates the schema/data, the 4 serving endpoints, the
Genie space, and the Lakebase instance; this script wires them into the app).

    python accelerator/wire_app.py                 # wire everything
    python accelerator/wire_app.py --dry-run        # print planned actions only
    python accelerator/wire_app.py --no-warm        # leave endpoints scale-to-zero

What it automates (each was a manual step before):
  1.  Discover the app service principal + Lakebase DNS + Genie space id.
  2.  UC grants to the app SP (USE_CATALOG / USE_SCHEMA / SELECT).
  3.  Lakebase Postgres grant — SET ROLE pg_database_owner; GRANT CREATE ON
      SCHEMA public (the `database` app-resource's CAN_CONNECT_AND_CREATE does
      NOT confer public CREATE on PG16; a plain GRANT by the deploying user only
      confers USAGE because `public` is owned by pg_database_owner).
  4.  Attach the app's full resource set (SQL warehouse, 4 serving endpoints →
      auto-grant CAN_QUERY, Ticketmaster secret → READ, Lakebase →
      CAN_CONNECT_AND_CREATE). This declares the COMPLETE set the app needs, so
      it also reconciles anything left over from an earlier `bundle deploy`.
  5.  Set GENIE_SPACE_ID in app.yaml from the created space.
  6.  Warm the serving endpoints (scale_to_zero=false) for responsive demos.
  7.  Enable AI/BI external embedding (for the Genie iframe).
  8.  Start + deploy the app, then poll /api/health.

Requires: the `databricks` CLI (authenticated to the target workspace via the
profile in customer_config.yaml) and `psql` on PATH. PyYAML for config parsing.

IMPORTANT: never run `databricks bundle deploy` AFTER wiring — it reconciles the
app to the resources declared in databricks.yml and WIPES the resources this
script attached. If you must redeploy the bundle, re-run this script afterwards.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ACC = REPO / "accelerator"
# The DAB bundle name is customer-namespaced (storesight-iq-<short_code>) so each
# customer deploys to an isolated bundle/root_path — derived per run in deploy_app.

DRY = False


def log(msg, sym="•"):
    print(f"  {sym} {msg}", flush=True)


def step(title):
    print(f"\n=== {title} ===", flush=True)


def load_cfg():
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML required: pip install pyyaml")
    p = ACC / "customer_config.yaml"
    if not p.exists():
        sys.exit(f"{p} not found — fill it (see customer_config.example.yaml) or run the interview first.")
    with open(p) as f:
        return yaml.safe_load(f)


# --- CLI helpers ------------------------------------------------------------
def _dbx(args, profile, json_out=True, check=True):
    """Run a databricks CLI command; return parsed JSON (or text)."""
    cmd = ["databricks"] + args + ["-p", profile]
    if json_out:
        cmd += ["-o", "json"]
    if DRY:
        log(f"[dry-run] {' '.join(cmd)}", "→")
        return {} if json_out else ""
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = "\n".join(l for l in res.stdout.splitlines() if "hostmetadata" not in l)
    if res.returncode != 0 and check:
        raise RuntimeError(f"CLI failed: {' '.join(cmd)}\n{res.stderr.strip()[:500]}\n{out[:500]}")
    if not json_out:
        return out
    try:
        return json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        return {"_raw": out, "_stderr": res.stderr}


def _dbx_json_stdin(args, profile, body):
    """databricks CLI call passing a JSON body via a temp file (--json @file)."""
    if DRY:
        log(f"[dry-run] databricks {' '.join(args)} --json '{json.dumps(body)[:200]}...'", "→")
        return {}
    tmp = Path("/tmp") / f"_wire_{abs(hash(json.dumps(body))) % 10**8}.json"
    tmp.write_text(json.dumps(body))
    try:
        return _dbx(args + ["--json", f"@{tmp}"], profile)
    finally:
        tmp.unlink(missing_ok=True)


# --- steps ------------------------------------------------------------------
def discover(cfg, profile):
    step("1. Discover workspace resources")
    app = cfg["app"]["name"]
    d = _dbx(["apps", "get", app], profile) or {}
    sp = d.get("service_principal_client_id")
    url = d.get("url")
    log(f"app: {app} | SP: {sp} | url: {url}")

    inst = cfg["lakebase"]["instance_name"]
    dbi = _dbx(["database", "get-database-instance", inst], profile) or {}
    dns = dbi.get("read_write_dns")
    log(f"lakebase: {inst} | dns: {dns}")

    space_name = cfg.get("genie", {}).get("space_name", "")
    spaces = _dbx(["genie", "list-spaces"], profile) or {}
    slist = spaces.get("spaces", spaces if isinstance(spaces, list) else [])
    space_id = next((s.get("space_id") or s.get("id") for s in slist
                     if s.get("title") == space_name), None)
    log(f"genie space '{space_name}': {space_id or 'NOT FOUND (run nb06 / setup_genie_space first)'}")

    me = _dbx(["current-user", "me"], profile) or {}
    user = me.get("userName", "")
    log(f"current user: {user}")
    return {"app": app, "sp": sp, "url": url, "dns": dns, "space_id": space_id, "user": user}


def uc_grants(cfg, profile, sp):
    step("2. Unity Catalog grants to the app SP")
    if not sp:
        log("no SP id — skipping", "!")
        return
    cat = cfg["databricks"]["catalog_name"]
    sch = f'{cat}.{cfg["databricks"]["schema_name"]}'
    _dbx_json_stdin(["grants", "update", "catalog", cat], profile,
                    {"changes": [{"principal": sp, "add": ["USE_CATALOG"]}]})
    log(f"granted USE_CATALOG on {cat}")
    _dbx_json_stdin(["grants", "update", "schema", sch], profile,
                    {"changes": [{"principal": sp, "add": ["USE_SCHEMA", "SELECT"]}]})
    log(f"granted USE_SCHEMA, SELECT on {sch}")


def lakebase_grant(cfg, profile, sp, dns, user):
    step("4. Lakebase Postgres grant (SET ROLE pg_database_owner → GRANT CREATE)")
    if not (sp and dns and user):
        log("missing sp/dns/user — skipping", "!")
        return
    db = cfg["lakebase"]["database_name"]
    conn = f"host={dns} port=5432 dbname={db} user={user} sslmode=require"
    # CRITICAL grant (must commit on its own). The app's _ensure_tables() needs
    # CREATE on schema public. These operate on objects owned by pg_database_owner,
    # so they always succeed.
    critical = (
        'SET ROLE pg_database_owner; '
        f'GRANT USAGE, CREATE ON SCHEMA public TO "{sp}"; '
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{sp}"; '
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO "{sp}";'
    )
    # BEST-EFFORT: re-grant on PRE-EXISTING tables/sequences. Only matters when a
    # Lakebase is REUSED across deploys (e.g. a restore) — its tables are then owned
    # by the connecting/deploying USER from the prior deploy, not the app SP. Two
    # things make this the SELF-HEALING step it needs to be:
    #   1. Run it AS THE CONNECTING USER — NOT `SET ROLE pg_database_owner`. Only a
    #      table's owner can GRANT on it; the connecting user owns the prior-deploy
    #      tables, pg_database_owner does not. (The earlier SET ROLE version silently
    #      skipped every foreign-owned table → the app got no write grant → inventory/
    #      prep submissions didn't persist.)
    #   2. Re-run it on EVERY wire. Re-attaching the database app-resource (which any
    #      `bundle deploy` forces) re-provisions the SP's Postgres role and RESETS its
    #      table grants, so re-wiring must re-apply them.
    # Kept SEPARATE and WITHOUT ON_ERROR_STOP: a table owned by yet another role just
    # gets skipped without aborting the critical CREATE grant (bundling them in one
    # implicit transaction would roll the critical grant back — the old persist bug).
    besteffort = (
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{sp}"; '
        f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{sp}";'
    )
    if DRY:
        log(f"[dry-run] psql '{conn}' -c \"{critical[:80]}...\" (then best-effort table grants)", "→")
        return
    token = _dbx(["auth", "token"], profile).get("access_token", "")
    env = {**os.environ, "PGPASSWORD": token}
    res = subprocess.run(["psql", conn, "-v", "ON_ERROR_STOP=1", "-c", critical],
                         capture_output=True, text=True, env=env)
    if res.returncode != 0:
        log(f"PG grant FAILED (is psql installed? is <user> the DB owner?): {res.stderr.strip()[:300]}", "!")
        return
    log(f"granted USAGE,CREATE on public to {sp} (+ default privileges)")
    # best-effort, non-fatal (own transaction, run as the connecting user; failures
    # here don't undo `critical`). Self-heals write grants on reused tables the
    # connecting user owns — re-provisioning on re-attach resets these otherwise.
    res2 = subprocess.run(["psql", conn, "-c", besteffort],
                          capture_output=True, text=True, env=env)
    if res2.returncode == 0:
        log(f"re-granted SELECT/INSERT/UPDATE/DELETE on existing tables to {sp} "
            "(self-heals reused-Lakebase persistence across re-attach)")
    else:
        log("existing-table grants skipped (any pre-existing tables are owned by "
            "neither you nor the app SP — the app owns the tables it creates, so "
            "this is usually fine)", "!")


def attach_resources(cfg, profile, app):
    step("3. Attach app resources (warehouse, endpoints, secret, Lakebase)")
    prefix = cfg["databricks"]["resource_prefix"]
    wh = cfg["databricks"].get("sql_warehouse_id", "")
    resources = [
        {"name": "sql_warehouse", "sql_warehouse": {"id": wh, "permission": "CAN_USE"}},
        {"name": "demand_forecast", "serving_endpoint": {"name": f"{prefix}-demand-forecast", "permission": "CAN_QUERY"}},
        {"name": "labor_optimizer", "serving_endpoint": {"name": f"{prefix}-labor-optimizer", "permission": "CAN_QUERY"}},
        {"name": "inventory_predictor", "serving_endpoint": {"name": f"{prefix}-inventory-predictor", "permission": "CAN_QUERY"}},
        {"name": "prep_scheduler", "serving_endpoint": {"name": f"{prefix}-prep-scheduler", "permission": "CAN_QUERY"}},
        {"name": "lakebase", "database": {
            "instance_name": cfg["lakebase"]["instance_name"],
            "database_name": cfg["lakebase"]["database_name"],
            "permission": "CAN_CONNECT_AND_CREATE"}},
    ]
    secret = (cfg.get("external_apis", {}) or {}).get("ticketmaster_secret", "") or ""
    if "/" in secret:
        scope, key = secret.split("/", 1)
        resources.append({"name": "ticketmaster_secret",
                          "secret": {"scope": scope, "key": key, "permission": "READ"}})
        log(f"including Ticketmaster secret {scope}/{key}")
    _dbx_json_stdin(["apps", "create-update", app], profile,
                    {"update_mask": "resources", "app": {"resources": resources}})
    log(f"attached {len(resources)} resources (SP auto-granted the declared permissions)")


def set_genie_env(space_id):
    step("5. Set GENIE_SPACE_ID in app.yaml")
    if not space_id:
        log("no space id — skipping (Genie iframe will be unconfigured)", "!")
        return
    p = REPO / "app.yaml"
    txt = p.read_text()
    import re
    # Match the GENIE_SPACE_ID env block by NAME, then replace whichever line
    # follows it — a literal `value: "..."` (including empty `value: ""`) OR a
    # legacy `valueFrom: "..."` (any target) — with the captured space id.
    new, n = re.subn(r'(- name:\s*"GENIE_SPACE_ID"\s*\n\s*)(?:value|valueFrom):\s*"[^"]*"',
                     rf'\g<1>value: "{space_id}"', txt)
    if n == 0:
        log("GENIE_SPACE_ID env block not found in app.yaml — set it manually", "!")
        return
    if new != txt and not DRY:
        p.write_text(new)
    log(f"GENIE_SPACE_ID = {space_id}" + (" [dry-run]" if DRY else ""))


def warm_endpoints(cfg, profile, warm):
    step("6. Endpoint warmth (scale_to_zero)")
    if not warm:
        log("--no-warm → leaving endpoints scale-to-zero (cheaper; cold-start latency)", "!")
        return
    prefix = cfg["databricks"]["resource_prefix"]
    for suffix in ("demand-forecast", "labor-optimizer", "inventory-predictor", "prep-scheduler"):
        ep = f"{prefix}-{suffix}"
        info = _dbx(["serving-endpoints", "get", ep], profile) or {}
        se = ((info.get("config") or {}).get("served_entities") or [{}])[0]
        name, ver = se.get("entity_name"), se.get("entity_version")
        if not name:
            log(f"{ep}: no served entity found — skipping", "!")
            continue
        _dbx_json_stdin(["serving-endpoints", "update-config", ep], profile,
                        {"served_entities": [{"entity_name": name, "entity_version": ver,
                                              "workload_size": "Small", "scale_to_zero_enabled": False}]})
        log(f"{ep}: warmed (scale_to_zero=false)")


def enable_embedding(profile):
    step("7. AI/BI external embedding (for the Genie iframe)")
    cur = _dbx(["settings", "aibi-dashboard-embedding-access-policy", "get"], profile) or {}
    pol = (cur.get("aibi_dashboard_embedding_access_policy") or {}).get("access_policy_type")
    etag = cur.get("etag")
    if pol == "ALLOW_ALL_DOMAINS":
        log("already ALLOW_ALL_DOMAINS")
        return
    _dbx_json_stdin(["settings", "aibi-dashboard-embedding-access-policy", "update"], profile,
                    {"allow_missing": True,
                     "field_mask": "aibi_dashboard_embedding_access_policy.access_policy_type",
                     "setting": {"aibi_dashboard_embedding_access_policy": {"access_policy_type": "ALLOW_ALL_DOMAINS"},
                                 "etag": etag, "setting_name": "default"}})
    log("set embedding policy to ALLOW_ALL_DOMAINS (requires workspace admin)")


def deploy_app(cfg, profile, app, user, url):
    step("8. Start + deploy the app, then verify /api/health")
    _dbx(["apps", "start", app], profile, check=False)
    bundle_name = f"storesight-iq-{cfg['customer']['short_code']}"
    src = f"/Workspace/Users/{user}/.bundle/{bundle_name}/files"
    # set_genie_env updated the LOCAL app.yaml, but `apps deploy` ships the synced
    # WORKSPACE copy — push app.yaml first, else GENIE_SPACE_ID never reaches the
    # deployed app and /api/health shows genie "not_configured".
    if not DRY:
        _dbx(["workspace", "import", f"{src}/app.yaml", "--file", str(REPO / "app.yaml"),
              "--format", "RAW", "--overwrite"], profile, json_out=False, check=False)
    _dbx(["apps", "deploy", app, "--source-code-path", src], profile, check=False)
    log(f"deployed app source from {src}")
    if DRY or not url:
        return
    token = _dbx(["auth", "token"], profile).get("access_token", "")
    for i in range(8):
        time.sleep(15)
        try:
            req = urllib.request.Request(f"{url}/api/health", headers={"Authorization": f"Bearer {token}"})
            body = urllib.request.urlopen(req, timeout=20).read().decode()
            if '"status"' in body:
                log(f"/api/health → {body[:160]}", "✓")
                return
        except Exception:
            pass
        log(f"waiting for app startup ({i+1}/8)…")
    log("app not healthy yet — check `databricks apps logs` (Lakebase/endpoints may still be warming)", "!")


def main():
    global DRY
    ap = argparse.ArgumentParser(description="Automated post-deploy wiring for StoreSight IQ.")
    ap.add_argument("--dry-run", action="store_true", help="Print planned actions without executing.")
    ap.add_argument("--no-warm", action="store_true", help="Leave serving endpoints scale-to-zero.")
    args = ap.parse_args()
    DRY = args.dry_run

    cfg = load_cfg()
    profile = cfg["databricks"]["profile"]
    print(f"{'DRY RUN — ' if DRY else ''}Wiring '{cfg['customer']['name']}' → profile '{profile}'")
    print("(Prereqs: bundle deployed + `storesight_setup` job run; catalog + SQL warehouse exist; "
          "profile has workspace-admin for the embedding setting.)")

    info = discover(cfg, profile)
    uc_grants(cfg, profile, info["sp"])
    # Attach the Lakebase `database` resource BEFORE the Postgres grant: attaching
    # it (CAN_CONNECT_AND_CREATE) is what provisions the app SP's Postgres role.
    # Running the grant first fails with `role "<sp>" does not exist`.
    attach_resources(cfg, profile, info["app"])
    lakebase_grant(cfg, profile, info["sp"], info["dns"], info["user"])
    set_genie_env(info["space_id"])
    warm_endpoints(cfg, profile, warm=not args.no_warm)
    enable_embedding(profile)
    deploy_app(cfg, profile, info["app"], info["user"], info["url"])

    print("\n" + "=" * 60)
    print("Wiring complete." if not DRY else "Dry run complete.")
    print("Do NOT `databricks bundle deploy` after this — it wipes the attached "
          "resources. Re-run this script if you must redeploy the bundle.")


if __name__ == "__main__":
    main()
