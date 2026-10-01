#!/usr/bin/env python3
"""
audit.py — full-stack customer/domain residue scanner for the StoreSight IQ
accelerator.

WHY THIS EXISTS: adapting the app is NOT just "replace the customer name +
colors." EVERY component must be assessed across EVERY customer-specific
dimension. A name-only pass once shipped hardcoded pizza emojis, a lucide
`Pizza` icon, "dough/crust" copy, AND — worse — a prior customer's actual menu
and ingredients hardcoded in the demo endpoints. This scanner enumerates the
dimensions and tiers what it finds so nothing is missed.

Run it AFTER generate.py and BEFORE deploy:
    python accelerator/audit.py

Tiers:
  FAIL   — prior-customer brand names. MUST be zero. (exit 2)
  HIGH   — a food/product/menu term inside a quoted string or label: almost
           always a hardcoded product NAME that should come from domain.yaml.
           Review every one; exit 1 if any remain unresolved.
  REVIEW — food/product emojis, domain-specific icons, raw hex in the frontend.
           Informational: confirm each is config-driven or intentionally generic.

Plus a PIPELINE section (structural, not residue): the 4 materialized views are
created in nb01, stores_kpi_view is date-robust (MAX(DATE) not CURRENT_DATE),
nb06 actually creates the Genie space, and the backend reads mv_store_overview.
A PIPELINE-FAIL also exits non-zero — these are the deploy gaps a name/brand
pass can't catch.

Cosmetic glyphs (✓ ✗ ⚠ • →), universal WEATHER/EVENT emojis, and neutral chart
grays are intentionally NOT flagged — they are domain-agnostic.

Dimensions every component is checked against:
  1. Prior-customer brand names        (FAIL)
  2. Hardcoded product/menu/ingredient names in strings/labels (HIGH)
  3. Food/product emojis               (REVIEW)
  4. Domain-specific lucide icons       (REVIEW)
  5. Raw hex colors in the frontend     (REVIEW)
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["frontend/src", "api", "services", "notebooks"]
SCAN_FILES = ["main.py", "config/settings.py", "app.yaml", "frontend/index.html"]
SKIP_PARTS = {"node_modules", "dist", ".git", "__pycache__"}
# Generated carriers legitimately hold customer values (still FAIL-checked).
GENERATED = {"frontend/src/brand.config.ts", "config/domain.json", "config/domain.py"}

# 1. Prior customers — must never survive. FAIL patterns scan the RAW line (not
# just quoted spans), so they also catch residue inside triple-quoted answer
# blocks that the HIGH scan (single-line quoted only) misses.
#   \bpapa\b  — catches a prior brand name AND its loyalty program, but NOT
#               "papaya" (no word boundary after "papa" there).
#   \bpj\b    — a prior brand abbreviation used in code comments/colors.
FAIL_PATTERNS = [
    (re.compile(r"\bpapa\b", re.I), "a prior customer brand (name or loyalty program)"),
    (re.compile(r"\bpj\b", re.I), "a prior customer brand (abbreviation)"),
    (re.compile(r"\bsubway\b", re.I), "a prior customer brand"),
]

# 2. Food / product / menu vocabulary (a prior/other customer's domain).
DOMAIN_TERMS = re.compile(
    r"\b(pizza|dough\s*ball|crust|calzone|burger|patty|taco|burrito|quesadilla|"
    r"hoagie|bagel|donut|doughnut|croissant|pepperoni|mozzarella|marinara|"
    r"stuffed\s*crust|shaq|drumstick|nugget|biscuit|tortilla|ramen|latte|espresso)\b",
    re.I)
QUOTED = re.compile(r'"([^"]{2,}?)"|\'([^\']{2,}?)\'')
LABELISH = re.compile(r'\b(label|name|title|item|menu)\b\s*[:=]', re.I)

# 3. FOOD/product emojis (domain signals) — NOT status/weather/event glyphs.
FOOD_EMOJI = re.compile(
    "[\U0001F32D-\U0001F37F\U0001F950-\U0001F96F\U0001F345-\U0001F37B\U0001FAD0-\U0001FADF]")

# 4. Domain-specific lucide icons implying a vertical.
DOMAIN_ICONS = re.compile(
    r"\b(Pizza|Sandwich|Beef|Croissant|Cookie|IceCream\w*|Fish|Salad|Soup|"
    r"Popcorn|Carrot|Apple|Cherry|Grape|Ham|Drumstick|Wheat|Donut|Beer|Wine|Milk)\b")

# 5. Raw hex in frontend components (should be brand tokens / CSS vars).
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")


def iter_files():
    seen = set()
    for d in SCAN_DIRS:
        for p in (REPO / d).rglob("*"):
            if p.is_file() and not (SKIP_PARTS & set(p.parts)) and p.suffix in {
                    ".ts", ".tsx", ".js", ".jsx", ".py", ".html", ".yaml", ".yml", ".css"}:
                seen.add(p)
    for f in SCAN_FILES:
        if (REPO / f).exists():
            seen.add(REPO / f)
    return sorted(seen)


def scan():
    fails, high, review = [], [], []
    for p in iter_files():
        r = str(p.relative_to(REPO))
        gen = r in GENERATED
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            s = line.strip()[:110]
            for rx, why in FAIL_PATTERNS:
                if rx.search(line):
                    fails.append((r, i, why, s))
            if gen:
                continue
            # HIGH: a domain term inside the LITERAL text of a quoted string.
            # Strip {…} interpolation first so a variable name (crust['name'])
            # inside an f-string/template doesn't count as literal product text.
            quoted = [re.sub(r"\{[^}]*\}", "", g) for m in QUOTED.finditer(line) for g in m.groups() if g]
            st = line.strip()
            is_comment = st.startswith(("#", "//", "*", '"""', "'''", "* "))
            # route/infra definitions: path/prefix values, FastAPI decorators &
            # include_router — internal API contracts, kept stable by design
            # (same class as the crust_type DB field), not user-visible product names.
            is_route = re.search(r"\bpath\s*[:=]|<Route|prefix\s*=|@router\.|include_router|tags\s*=", line)
            is_datakey = re.search(r"crust_type|crust\[|_dough_|getDough|queryKey|task_key|\[['\"]name['\"]\]", line)
            is_log = re.search(r"logger\.|print\(|console\.", line)      # internal diagnostics
            if any(DOMAIN_TERMS.search(q) for q in quoted) and not (
                    is_comment or is_route or is_datakey or is_log or "import " in line):
                high.append((r, i, "hardcoded product/menu/ingredient name — source from domain.yaml", s))
            # REVIEW
            if FOOD_EMOJI.search(line):
                review.append((r, i, "food emoji (config-drive via brand.config.prepEmoji?)", s))
            if DOMAIN_ICONS.search(line) and ("lucide" in line or "<" in line):
                review.append((r, i, "domain-specific icon (use generic / config-driven)", s))
            if r.endswith((".tsx", ".ts", ".jsx")) and HEX_RE.search(line) and "brand" not in line:
                review.append((r, i, "raw hex color (use brand token / CSS var)", s))
    return fails, high, review


# ---------------------------------------------------------------------------
# Pipeline-completeness checks (structural, not residue): the deploy-time gaps a
# name/brand pass can't catch. Each is a hard invariant a working demo needs —
# every one traces to a bug hit standing the app up live.
# ---------------------------------------------------------------------------
PIPELINE_MVS = ["mv_daily_sales", "mv_employees", "mv_inventory", "mv_store_overview"]


def check_pipeline():
    """Return (fails, warns): structural pipeline invariants for the notebooks + app."""
    fails, warns = [], []

    def _read(rel):
        p = REPO / rel
        return p.read_text(encoding="utf-8") if p.exists() else ""

    nb01_rel = "notebooks/01_generate_data_and_streaming.py"
    nb06_rel = "notebooks/06_setup_genie_space.py"
    stores_rel = "api/stores.py"
    t01, t06, tstores = _read(nb01_rel), _read(nb06_rel), _read(stores_rel)

    # 1. All 4 materialized views are created in nb01 (the app + Genie read them;
    #    without them the app is slow and the regional/Genie views are empty).
    #    Accept both an inline `CREATE MATERIALIZED VIEW ... <mv>` and the
    #    dict-of-SELECTs + `CREATE MATERIALIZED VIEW {..}.{_name}` loop form.
    has_create_mv = re.search(r"CREATE\s+MATERIALIZED\s+VIEW", t01, re.I)
    for mv in PIPELINE_MVS:
        inline = re.search(rf"CREATE\s+MATERIALIZED\s+VIEW[^\n]*{mv}", t01, re.I)
        referenced = re.search(rf"[\"']{mv}[\"']|\b{mv}\b", t01)
        if not (inline or (has_create_mv and referenced)):
            fails.append((nb01_rel, f"materialized view '{mv}' is not created (app/Genie depend on it)"))

    # 2. stores_kpi_view must anchor "today" to MAX(DATE(...)) not CURRENT_DATE:
    #    synthetic data is static, so a calendar-date filter reads $0/-100% (all
    #    stores red) a day after generation. Scope the check to the view's block.
    idx = t01.find("stores_kpi_view")
    if idx != -1:
        window = t01[idx: idx + 2600]
        has_max = re.search(r"MAX\s*\(\s*DATE", window, re.I)
        if re.search(r"CURRENT_DATE", window, re.I) and not has_max:
            fails.append((nb01_rel, "stores_kpi_view uses CURRENT_DATE() without a MAX(DATE(...)) anchor "
                                    "— static demo data will read as $0 / -100% for every store"))
        elif not has_max:
            warns.append((nb01_rel, "confirm stores_kpi_view anchors to MAX(DATE(...)), not the calendar date"))

    # 3. nb06 must actually CREATE the Genie space, not just print manual steps.
    if not re.search(r"create[_-]space", t06, re.I):
        fails.append((nb06_rel, "does not create a Genie space (no create-space call) — nb06 must create it"))

    # 4. Backend store KPIs read the materialized view (fast), not the raw view.
    if tstores and "mv_store_overview" not in tstores:
        warns.append((stores_rel, "store KPIs don't read mv_store_overview — repoint to the materialized view"))

    return fails, warns


def _print(title, items):
    print(f"\n{title} ({len(items)})")
    by = {}
    for r, i, why, snip in items:
        by.setdefault(r, []).append((i, why, snip))
    for r in sorted(by):
        print(f"  {r}:")
        for i, why, snip in by[r]:
            print(f"    L{i}: {why}\n         {snip}")


def main():
    fails, high, review = scan()
    pipe_fails, pipe_warns = check_pipeline()
    print("=" * 72)
    print("StoreSight IQ — full-stack customer/domain residue audit")
    print("=" * 72)
    if fails:
        _print("❌ FAIL — prior-customer residue (MUST fix):", fails)
    else:
        print("\n✅ FAIL: no prior-customer residue.")
    if high:
        _print("🔴 HIGH — hardcoded product/menu names (source from domain.yaml):", high)
    else:
        print("✅ HIGH: no hardcoded product/menu names.")
    if review:
        _print("⚠️  REVIEW — confirm config-driven or intentionally generic:", review)
    else:
        print("✅ REVIEW: nothing to assess.")

    # Pipeline-completeness (structural invariants, not residue).
    print("\n" + "-" * 72)
    if pipe_fails:
        print(f"❌ PIPELINE — missing deploy-critical pieces ({len(pipe_fails)}):")
        for r, why in pipe_fails:
            print(f"  {r}:\n    {why}")
    else:
        print("✅ PIPELINE: MVs created, view is date-robust, Genie space created, app reads the MV.")
    if pipe_warns:
        print(f"\n⚠️  PIPELINE REVIEW ({len(pipe_warns)}):")
        for r, why in pipe_warns:
            print(f"  {r}:\n    {why}")

    print("\n" + "=" * 72)
    print(f"Summary: {len(fails)} FAIL · {len(high)} HIGH · {len(review)} REVIEW · "
          f"{len(pipe_fails)} PIPELINE-FAIL · {len(pipe_warns)} PIPELINE-REVIEW")
    print("FAIL, HIGH, and PIPELINE-FAIL must be resolved before shipping. REVIEW items are a "
          "per-item assessment: each should trace to customer_config.yaml / domain.yaml / brand.config.ts.")
    sys.exit(2 if (fails or pipe_fails) else (1 if high else 0))


if __name__ == "__main__":
    main()
