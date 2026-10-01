#!/usr/bin/env python3
"""
generate.py — apply a filled customer_config.yaml + domain.yaml to the repo.

This is the accelerator's engine: it takes the two config files (filled by the
guided interview or by hand) and rewrites every place a QSR customer's brand,
naming, and taxonomy live — so the human never hand-edits code.

    python accelerator/generate.py \
        --config accelerator/customer_config.yaml \
        --domain accelerator/domain.yaml

Design notes:
  * IDEMPOTENT — every write is a targeted regex/section replace that also
    matches its own previous output, so re-running with an updated config
    re-applies cleanly (no drift, no double-insertion).
  * The product TAXONOMY (domain.yaml) is emitted verbatim to config/domain.json,
    which the backend AND notebooks load at runtime — one source, no ML
    feature-contract drift.
  * NAMING for notebooks is passed by the DAB as job parameters (widgets), not
    baked here — so notebooks are never rewritten per customer.
  * Requires PyYAML (a build-time tool dependency, not an app dependency):
    pip install pyyaml
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ACC = REPO / "accelerator"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML is required: pip install pyyaml")
    if not path.exists():
        sys.exit(f"Config not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def hex_to_rgb(h: str) -> str:
    h = h.strip().lstrip("#")
    if len(h) != 6:
        return "45, 107, 224"
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


class Patcher:
    """Tracks edits and supports --dry-run."""

    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.changed: list[str] = []
        self.skipped: list[str] = []

    def apply(self, rel: str, subs: list[tuple[str, str]], flags=re.M):
        path = REPO / rel
        if not path.exists():
            self.skipped.append(f"{rel} (missing)")
            return
        text = orig = path.read_text()
        for pat, repl in subs:
            text = re.sub(pat, repl, text, flags=flags)
        if text != orig:
            if not self.dry_run:
                path.write_text(text)
            self.changed.append(rel)
        else:
            self.skipped.append(f"{rel} (no change)")

    def write(self, rel: str, content: str):
        path = REPO / rel
        if path.exists() and path.read_text() == content:
            self.skipped.append(f"{rel} (no change)")
            return
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.changed.append(rel)

    def copy(self, src: Path, rel_dst: str):
        dst = REPO / rel_dst
        # Idempotent: skip if the destination already matches the source.
        if dst.exists() and src.exists() and dst.read_bytes() == src.read_bytes():
            self.skipped.append(f"{rel_dst} (no change)")
            return
        if not self.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        self.changed.append(f"{rel_dst} (copied from {src})")


def _lit(s) -> str:
    """Escape a config value for safe use in a regex replacement string."""
    return str(s).replace("\\", "\\\\")


def _js_squote(s) -> str:
    """Escape a config value for a SINGLE-quoted JS/TS string literal, then for
    a regex replacement string. Without this a customer name with an apostrophe
    (e.g. "Mama's") terminates the literal and breaks the TS build."""
    body = str(s).replace("\\", "\\\\").replace("'", "\\'")
    return body.replace("\\", "\\\\")


# Naming fields feed SQL identifiers (schema/catalog), DAB bundle+target names,
# and workspace-unique resource names (endpoints / lakebase / app). An apostrophe
# or space in ANY of them re-creates the "Mama's" build/SQL break one layer down
# — and unlike the DISPLAY name (customer.name, handled by _js_squote), these are
# never escaped, they're used raw. So enforce identifier-safety here rather than
# trusting the human to type a clean token. This is the guardrail that makes
# "Mama's" -> short_code `mamas` -> schema `storesight_iq_mamas` a guarantee,
# not a convention.
_NAMING_RULES = {
    # field path in customer_config -> (regex, human description)
    ("customer", "short_code"): (
        r"^[a-z][a-z0-9]*$",
        "lowercase letters/digits, starting with a letter (e.g. 'mamas') — it "
        "namespaces the bundle, DAB target, schema and every resource",
    ),
    ("databricks", "catalog_name"): (
        r"^[A-Za-z_][A-Za-z0-9_]*$",
        "an unquoted SQL identifier: letters/digits/underscore, no spaces or apostrophes",
    ),
    ("databricks", "schema_name"): (
        r"^[A-Za-z_][A-Za-z0-9_]*$",
        "an unquoted SQL identifier: letters/digits/underscore, no spaces or apostrophes "
        "(e.g. 'storesight_iq_mamas')",
    ),
    ("databricks", "resource_prefix"): (
        r"^[a-z][a-z0-9-]*$",
        "lowercase letters/digits/hyphens (DNS-style) — it names serving endpoints, "
        "the Lakebase instance and the app (e.g. 'storesight-mamas')",
    ),
}


def validate_naming(cfg: dict):
    """Fail fast if any naming field would produce a broken SQL/DAB identifier.

    The DISPLAY name (customer.name) may contain anything — apostrophes included —
    because _js_squote escapes it. But the NAMING fields below are used RAW in SQL
    DDL, the DAB bundle/target, and workspace-unique resource names, so a stray
    apostrophe/space there is a hard error waiting to happen. Catch it at generate
    time with an actionable message instead of at `bundle deploy` / notebook run."""
    problems = []
    for (section, key), (pattern, desc) in _NAMING_RULES.items():
        val = (cfg.get(section) or {}).get(key)
        if val is None:
            continue  # optional/derived fields validate elsewhere; don't invent errors
        if not re.match(pattern, str(val)):
            problems.append(f"  ✗ {section}.{key} = {val!r}\n      must be {desc}")
    # app.name is optional (derived from resource_prefix); validate only if set.
    app_name = (cfg.get("app") or {}).get("name")
    if app_name is not None and not re.match(r"^[a-z][a-z0-9-]*$", str(app_name)):
        problems.append(
            f"  ✗ app.name = {app_name!r}\n      must be lowercase letters/digits/hyphens "
            "(a workspace-unique Databricks Apps name)"
        )
    if problems:
        sys.exit(
            "Invalid naming in customer_config.yaml — these fields become SQL/DAB "
            "identifiers and cannot contain spaces, apostrophes, or uppercase where "
            "noted.\nThe brand DISPLAY name (customer.name) is exempt — put "
            '"Mama\'s" there; keep short_code/schema/prefix clean lowercase tokens.\n\n'
            + "\n".join(problems)
        )


# ---------------------------------------------------------------------------
# generation steps
# ---------------------------------------------------------------------------
def emit_domain_json(dom: dict, p: Patcher):
    """domain.yaml -> config/domain.json (verbatim; the runtime taxonomy)."""
    out = {"_comment": "GENERATED by accelerator/generate.py from domain.yaml — do not hand-edit."}
    out.update(dom)
    p.write("config/domain.json", json.dumps(out, indent=2) + "\n")


def patch_settings(cfg: dict, p: Patcher):
    db, lb, ms = cfg["databricks"], cfg["lakebase"], cfg["model_serving"]

    def field(name, val):
        # (attr:...Field(  default=)"..." -> new  (scoped to the named field)
        return (
            rf'({name}[^\n]*=\s*Field\(\s*\n\s*default=)"[^"]*"',
            rf'\g<1>"{_lit(val)}"',
        )

    p.apply("config/settings.py", [
        field("catalog_name", db["catalog_name"]),
        field("schema_name", db["schema_name"]),
        field("lakebase_instance_name", lb["instance_name"]),
        field("lakebase_database_name", lb["database_name"]),
        field("demand_forecast_endpoint", ms["demand_forecast"]),
        field("labor_optimizer_endpoint", ms["labor_optimizer"]),
        field("inventory_predictor_endpoint", ms["inventory_predictor"]),
        field("prep_scheduler_endpoint", ms["prep_scheduler"]),
        field("workspace_id", db["workspace_id"]),
    ])


def patch_app_yaml(cfg: dict, p: Patcher):
    db, lb, ms, ext = cfg["databricks"], cfg["lakebase"], cfg["model_serving"], cfg.get("external_apis", {})

    def env(name, val):
        # - name: "NAME"\n  value: "..." -> new value
        return (
            rf'(- name: "{name}"\s*\n\s*value: )"[^"]*"',
            rf'\g<1>"{_lit(val)}"',
        )

    subs = [
        env("CATALOG_NAME", db["catalog_name"]),
        env("SCHEMA_NAME", db["schema_name"]),
        env("LAKEBASE_INSTANCE_NAME", lb["instance_name"]),
        env("LAKEBASE_DATABASE_NAME", lb["database_name"]),
        env("DEMAND_FORECAST_ENDPOINT", ms["demand_forecast"]),
        env("LABOR_OPTIMIZER_ENDPOINT", ms["labor_optimizer"]),
        env("INVENTORY_PREDICTOR_ENDPOINT", ms["inventory_predictor"]),
        env("PREP_SCHEDULER_ENDPOINT", ms["prep_scheduler"]),
        env("WORKSPACE_ID", str(db["workspace_id"])),
    ]
    p.apply("app.yaml", subs)


def patch_ticketmaster(cfg: dict, p: Patcher):
    """Toggle the Ticketmaster app-env in app.yaml based on whether a secret is set.
    (Events still render without it — the backend synthesizes fallback events.)"""
    secret = (cfg.get("external_apis", {}) or {}).get("ticketmaster_secret", "") or ""
    active = '  - name: "TICKETMASTER_API_KEY"\n    valueFrom: "ticketmaster_secret"'
    commented = '  # - name: "TICKETMASTER_API_KEY"\n  #   valueFrom: "ticketmaster_secret"'
    target = (active if secret else commented).replace("\\", "\\\\")
    # normalize whichever form is present to the target form (idempotent)
    p.apply("app.yaml", [(re.escape(commented), target), (re.escape(active), target)], flags=0)


def patch_index_css(cfg: dict, p: Patcher):
    b = cfg["brand"]
    def var(name, val):
        return (rf'(--{name}:\s*)#[0-9A-Fa-f]{{6}}', rf'\g<1>{val}')
    subs = [
        var("brand-primary", b["primary_hex"]),
        var("brand-primary-dark", b["primary_dark_hex"]),
        var("brand-primary-light", b["primary_light_hex"]),
        var("brand-secondary", b["secondary_hex"]),
        var("brand-secondary-dark", b["secondary_dark_hex"]),
        var("brand-secondary-light", b["secondary_light_hex"]),
        (r'(--brand-primary-rgb:\s*)[0-9, ]+;', rf'\g<1>{hex_to_rgb(b["primary_hex"])};'),
    ]
    p.apply("frontend/src/index.css", subs)


def patch_brand_config_ts(cfg: dict, dom: dict, p: Patcher, logo_src: str, mark_src: str):
    c = cfg["customer"]
    prep = dom.get("prep", {})
    prep_enabled = bool(cfg.get("features", {}).get("prep_scheduler_enabled", True))
    def kv(key, val):
        # Match a single-quoted TS literal INCLUDING escaped quotes (\'), so a
        # re-run stays idempotent for apostrophe customers. A plain [^']* would
        # stop at the escaped quote in 'Mama\'s', treat it as the closing quote,
        # and duplicate the tail on every re-run ('Mama\'s' -> 'Mama\'s's').
        return (rf"({key}: ')(?:[^'\\]|\\.)*'", rf"\g<1>{_js_squote(val)}'")
    p.apply("frontend/src/brand.config.ts", [
        kv("customerName", c["name"]),
        kv("productName", c.get("product_name", "StoreSight IQ")),
        kv("tagline", c.get("tagline", "Store Operations Intelligence")),
        kv("logoSrc", logo_src),
        kv("markSrc", mark_src),
        # prep-vertical vocabulary (drives icon-emoji + nouns on the prep page)
        kv("prepEmoji", prep.get("emoji", "🍽️")),
        kv("prepNoun", prep.get("item_noun", "prep batch")),
        kv("prepNounPlural", prep.get("item_noun_plural", "prep batches")),
        kv("prepPageTitle", prep.get("page_title", "Prep Scheduler")),
        # Boolean (unquoted) — whether the 5th prep-scheduler surface ships.
        (r"(prepSchedulerEnabled:\s*)(?:true|false)", rf"\g<1>{'true' if prep_enabled else 'false'}"),
    ])


def copy_logos(cfg: dict, p: Patcher):
    """Copy customer logos into frontend/public; return (logoSrc, markSrc)."""
    b = cfg["brand"]
    logo_src, mark_src = "/brand-logo.svg", "/brand-mark.svg"
    for key, target_stem, out_var in (("logo_path", "brand-logo", "logo"),
                                      ("logo_circle_path", "brand-mark", "mark")):
        rel = b.get(key)
        if not rel:
            continue
        src = (REPO / rel) if not Path(rel).is_absolute() else Path(rel)
        if not src.exists():
            p.skipped.append(f"logo {rel} (not found — keeping placeholder)")
            continue
        ext = src.suffix or ".svg"
        dst_rel = f"frontend/public/{target_stem}{ext}"
        p.copy(src, dst_rel)
        if out_var == "logo":
            logo_src = f"/{target_stem}{ext}"
        else:
            mark_src = f"/{target_stem}{ext}"
    return logo_src, mark_src


def patch_index_html(cfg: dict, p: Patcher, mark_src: str):
    c = cfg["customer"]
    mime = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".ico": "image/x-icon", ".webp": "image/webp"}.get(
        Path(mark_src).suffix.lower(), "image/svg+xml")
    p.apply("frontend/index.html", [
        (r'<title>[^<]*</title>', f'<title>{c.get("product_name","StoreSight IQ")} | {c["name"]}</title>'),
        (r'(<meta name="description" content=)"[^"]*"',
         rf'\g<1>"{c.get("product_name","StoreSight IQ")} - {_lit(c.get("tagline","Store Operations Intelligence"))}"'),
        # rewrite the whole favicon link so type matches the mark's extension
        (r'<link rel="icon"[^>]*/>', f'<link rel="icon" type="{mime}" href="{mark_src}" />'),
        (r'(class="loader-logo" src=)"/brand-mark\.[a-z]+"', rf'\g<1>"{mark_src}"'),
    ])


def patch_layout_stores(dom: dict, p: Patcher):
    """Regenerate the STORES / ALL_STORES arrays in both layouts from domain."""
    stores = dom.get("stores", [])
    rows = "\n".join(
        f'  {{ id: {s["id"]}, name: "{s["name"]}", city: "{s.get("city","")}" }},'
        for s in stores
    )
    for rel, var in (("frontend/src/layouts/StoreLayout.tsx", "STORES"),
                     ("frontend/src/layouts/RegionalLayout.tsx", "ALL_STORES")):
        block = f"const {var} = [\n{rows}\n]"
        # match `const VAR = [ ... \n]` (array closes on a line that is just ])
        p.apply(rel, [(rf'const {var} = \[.*?\n\]', block.replace("\\", "\\\\"))], flags=re.S)


def patch_mapview_initial_view(dom: dict, p: Patcher):
    """Bake the fleet centroid + a fitted zoom into MapView's INITIAL_VIEW_STATE so
    the regional map opens framed on the customer's geography for ANY customer.
    (A runtime auto-fit effect exists too but can't be relied on for first paint.)"""
    stores = [s for s in dom.get("stores", []) if s.get("lat") is not None and s.get("lng") is not None]
    if not stores:
        return
    lats = [float(s["lat"]) for s in stores]
    lngs = [float(s["lng"]) for s in stores]
    clat, clng = sum(lats) / len(lats), sum(lngs) / len(lngs)
    span = max(max(lats) - min(lats), max(lngs) - min(lngs))
    # pick a zoom that frames the fleet's bounding box (empirical thresholds)
    zoom = (10.0 if span <= 0.35 else 9.2 if span <= 0.7 else 8.3 if span <= 1.5
            else 7.0 if span <= 3 else 5.5 if span <= 8 else 4.2 if span <= 20 else 3.5)
    block = (f"const INITIAL_VIEW_STATE = {{\n"
             f"  longitude: {round(clng, 4)},\n"
             f"  latitude: {round(clat, 4)},\n"
             f"  zoom: {zoom},\n"
             f"  pitch: 45,\n"
             f"  bearing: 0,\n"
             f"}}")
    p.apply("frontend/src/pages/regional/MapView.tsx",
            [(r"const INITIAL_VIEW_STATE = \{.*?\n\}", block.replace("\\", "\\\\"))], flags=re.S)


def patch_databricks_yml(cfg: dict, p: Patcher):
    """Fill the DAB variable defaults + target host from the manifest."""
    db = cfg["databricks"]
    app_name = cfg.get("app", {}).get("name", f"storesight-{db['short_code'] if 'short_code' in db else cfg['customer']['short_code']}")

    def vardef(name, val):
        # replace the `default:` line inside a named top-level variable block
        return (rf'(^  {name}:\n(?:    .*\n)*?    default: ).*$', rf'\g<1>{_lit(val)}')

    # CRITICAL ISOLATION (both are required — one alone is NOT enough):
    #  (1) bundle.name → storesight-iq-<short_code>. `bundle.name` can't use vars,
    #      so write the literal. It scopes the REMOTE terraform state root_path
    #      (${bundle.name}).
    #  (2) the TARGET name → <short_code> (not the shared "dev"). The LOCAL terraform
    #      state cache is `.databricks/bundle/<TARGET>/terraform.tfstate`, keyed by
    #      target, and it persists in the working dir across git branches. If two
    #      customers share a target (e.g. "dev") in one working dir, the 2nd deploy
    #      reconciles the 1st's state and DELETES its schema/app/jobs — this is the
    #      exact bug that clobbered a prior customer TWICE. Namespacing bundle.name
    #      alone does NOT fix it; the target must be unique too.
    # (Also deploy each customer from a SEPARATE working dir/worktree as belt-and-
    #  suspenders — see WORKSPACE_STEPS.md.)
    short = cfg["customer"]["short_code"]
    p.apply("databricks.yml", [
        (r'(^bundle:\n  name: ).*$', rf'\g<1>storesight-iq-{_lit(short)}'),
        # rename the (single, default) target key to the customer short_code
        (r'(^targets:\n(?:  #.*\n)*  )[A-Za-z0-9_-]+(:\n    default: true)', rf'\g<1>{_lit(short)}\g<2>'),
        vardef("catalog", db["catalog_name"]),
        vardef("schema", db["schema_name"]),
        vardef("resource_prefix", db["resource_prefix"]),
        vardef("warehouse_id", db.get("sql_warehouse_id", "") or '""'),
        vardef("app_name", app_name),
        (r'(^      host: ).*$', rf'\g<1>{_lit(db["workspace_host"])}'),
    ])


def patch_inventory_categories(dom: dict, p: Patcher):
    """Regenerate the Inventory category filter tabs from domain ingredient_categories."""
    cats = list((dom.get("ingredient_categories") or {}).keys())
    rows = ["  { key: null, label: 'All' },"]
    for k in cats:
        label = k.replace("_", " ").title()
        rows.append(f"  {{ key: '{k}', label: '{label}' }},")
    block = "const categories = [\n" + "\n".join(rows) + "\n]"
    p.apply("frontend/src/pages/store/Inventory.tsx",
            [(r"const categories = \[.*?\n\]", block.replace("\\", "\\\\"))], flags=re.S)


def patch_notebook_widget_defaults(cfg: dict, p: Patcher):
    """Set the DEFAULT values of the notebook config widgets (DAB overrides at run)."""
    db = cfg["databricks"]
    genie = cfg.get("genie", {}) or {}
    subs = [
        (r'(dbutils\.widgets\.text\("catalog",\s*)"[^"]*"', rf'\g<1>"{_lit(db["catalog_name"])}"'),
        (r'(dbutils\.widgets\.text\("schema",\s*)"[^"]*"', rf'\g<1>"{_lit(db["schema_name"])}"'),
        (r'(dbutils\.widgets\.text\("resource_prefix",\s*)"[^"]*"', rf'\g<1>"{_lit(db["resource_prefix"])}"'),
        # nb06 declares a warehouse_id widget (Genie create-space needs it). The
        # DAB passes it at run time; this sets a useful default for standalone runs.
        # No-op on notebooks that don't declare the widget.
        (r'(dbutils\.widgets\.text\("warehouse_id",\s*)"[^"]*"', rf'\g<1>"{_lit(db.get("sql_warehouse_id", ""))}"'),
        # nb06 Genie space title/description. CRITICAL: the title MUST match
        # customer_config.genie.space_name so wire_app.py can find the space it
        # creates and set GENIE_SPACE_ID. Without this the space keeps the neutral
        # title and the Genie iframe never gets wired for a real customer.
        (r'(dbutils\.widgets\.text\("genie_space_name",\s*)"[^"]*"', rf'\g<1>"{_lit(genie.get("space_name", ""))}"'),
        (r'(dbutils\.widgets\.text\("genie_description",\s*)"[^"]*"', rf'\g<1>"{_lit(genie.get("description", ""))}"'),
    ]
    for nb in sorted((REPO / "notebooks").glob("0*.py")):
        p.apply(f"notebooks/{nb.name}", subs)
    # The teardown notebook lives in setup/ and reads the same widgets (esp.
    # genie_space_name), so patch its defaults too.
    for s in sorted((REPO / "setup").glob("*.py")):
        p.apply(f"setup/{s.name}", subs)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Apply customer_config.yaml + domain.yaml to the repo.")
    ap.add_argument("--config", default=str(ACC / "customer_config.yaml"))
    ap.add_argument("--domain", default=str(ACC / "domain.yaml"))
    ap.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    dom = load_yaml(Path(args.domain))
    validate_naming(cfg)  # fail fast on apostrophe/space in schema/bundle/prefix names
    p = Patcher(args.dry_run)

    emit_domain_json(dom, p)
    logo_src, mark_src = copy_logos(cfg, p)
    patch_brand_config_ts(cfg, dom, p, logo_src, mark_src)
    patch_index_css(cfg, p)
    patch_index_html(cfg, p, mark_src)
    patch_settings(cfg, p)
    patch_app_yaml(cfg, p)
    patch_ticketmaster(cfg, p)
    patch_layout_stores(dom, p)
    patch_mapview_initial_view(dom, p)
    patch_inventory_categories(dom, p)
    patch_notebook_widget_defaults(cfg, p)
    patch_databricks_yml(cfg, p)

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Applied config for '{cfg['customer']['name']}' ({cfg['customer']['short_code']})")
    print(f"\nChanged ({len(p.changed)}):")
    for c in p.changed:
        print(f"  ✓ {c}")
    if p.skipped:
        print(f"\nUnchanged/skipped ({len(p.skipped)}):")
        for s in p.skipped:
            print(f"  · {s}")
    print("\nNext: rebuild the frontend (cd frontend && npm run build), then "
          "`databricks bundle deploy` + `bundle run`, then `python accelerator/wire_app.py "
          "-p <profile>` to wire the workspace automatically. See accelerator/WORKSPACE_STEPS.md.")


if __name__ == "__main__":
    main()
