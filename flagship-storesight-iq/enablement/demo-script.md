# StoreSight IQ — Demo Script

A **tell → show → tell** playbook for demoing StoreSight IQ. This is a *framework
with cues and flow*, not a word-for-word script — adapt the language to your
audience and let the product carry the story.

- **Audience:** operations / IT / data leaders at any multi-site business
  (QSR, retail, CPG, hospitality, travel).
- **Length:** ~15–20 min (10 min show, ~5 min bookends). Trim tabs as needed.
- **Setup:** deploy the demo first (see `../README.md` + `../accelerator/WORKSPACE_STEPS.md`),
  open the app, and have the **pitch deck** (`storesight-iq-pitch-deck.html`) ready
  in another tab/full-screen. Optional: skim the **demo video** (`README.md` in
  this folder) beforehand to see the flow end-to-end.

> **The arc:** the deck frames the problem and the three capabilities (TELL), the
> app proves each one live (SHOW), and you close by mapping what they saw back to
> those capabilities and the business value (TELL).

---

## Part 1 — TELL: frame the problem & the promise (pitch deck, ~3 min)

**Slide 1 — "Multi-site operators are flying blind."**
Set the stage: any business running many sites shares one problem — operations
sprawl across locations and systems, so the data that should drive decisions is
scattered and out of reach. Walk the three pains (they map 1:1 to what you'll show):
1. **Blind, no real time** — no unified 360° view; every site is run from
   yesterday's reports.
2. **Operations run on guesswork** — no forward-looking view of demand, labor, or
   inventory; every call is a gut call.
3. **Answers take days** — no self-service analytics; every question is a BI ticket.

Cue: land one stat that fits the room (e.g. *~73% of enterprise data goes unused*,
or *up to 65% fewer lost sales when AI forecasting replaces gut feel*).

**Slide 2 — "StoreSight IQ."**
Introduce the answer as three capabilities, and promise you'll show each live:
1. **Unified Operations** — real-time, descriptive.
2. **Forward-Looking Planning** — predictive → prescriptive.
3. **Decision Intelligence** — self-service, natural-language.

Cue: note it's **built once on Databricks** — Unity Catalog, SQL Warehouse,
MLflow + Model Serving, Lakebase, Genie, and Apps — and deployable for any
distributed operator. Then transition: *"Let me show you."*

---

## Part 2 — SHOW: the product, live (~10 min)

### Home — two personas
Open on the landing page. Point out the two entry points: **Store Manager** (running
a single site day-to-day) and **Regional Manager** (overseeing the fleet). *"We'll
start in the store manager's shoes, then zoom out to the region."* Enter as the
**Store Manager**.

### 1. Operations — the unified, real-time view *(capability: Unified Operations)*
This is the 360° store view the first slide said was missing. Call out the live
descriptive analytics — sales, channel mix, and foot traffic **as they happen**,
not yesterday's report. Highlight the **real, live external signals**: current
**weather** and nearby **local events** pulled in live — the context that actually
moves foot traffic. Cue: *"Every tile here is a live query against Unity Catalog
through a SQL Warehouse — one place the operational data finally comes together."*

### 2. Forecast — predict the demand *(capability: Forward-Looking Planning — predictive)*
Move from "what's happening" to "what's about to happen." Show the **daily and
hourly foot-traffic forecast**. Cue: *"This isn't a spreadsheet trend line — it's
an ML model trained and served on Databricks (MLflow + Model Serving), scoring
demand for this store."* Tie it back: this is the antidote to "operations run on
guesswork."

### 3. Labor — staff to the demand *(prescriptive)*
Natural next question: *"Now that I know demand, how do I staff for it?"* Show the
recommended staffing by daypart against the forecast — enough hands at the lunch
rush, not overstaffed in the lull. Cue: *"Forecast turns into a labor plan — the
predictive becomes prescriptive."*

### 4. Inventory — stock to the demand *(prescriptive + write-back)*
The other side of meeting demand: having the right amount of each ingredient. Show
current stock vs. par and the **ML reorder suggestions**. Then **act**: review a
suggestion and **place the order**. Cue: *"When I approve this, it writes straight
to our operational database — **Lakebase**, Postgres-native on Databricks — so the
app isn't just analytics, it's a system of action."*

### 5. Kitchen Prep — prep to the demand *(prescriptive + write-back)*
The freshness lever: *"Based on expected demand, how much of each item should we
prep, and when, so food is fresh — not made too early or too late?"* Show the
prep recommendations by time window, **review the ML suggestion, and approve the
schedule** — again noting it **writes back to Lakebase**. Cue: *"Same pattern —
predict, recommend, act."*

> Transition: *"That's the single-site operator's day. Now let's step up to the
> person running the whole region."* Switch to the **Regional Manager** view.

### 6. Store Map — the fleet at a glance *(capability: Unified Operations, at scale)*
Show the interactive **map of every store in the region**, surfaced with the KPIs a
regional leader cares about — one unified view of the fleet instead of a stack of
per-store reports. Click a store to drill in.

### 7. Compare + Genie — ask the "why" in plain language *(capability: Decision Intelligence)*
Open the **Compare / Genie** tab. This is the payoff to slide 1's "answers take
days." Ask a plain-language question and get an answer in seconds — no BI ticket,
no analyst queue. Suggested asks (pick 1–2 that land):
- *"Which stores are underperforming this month, and why?"*
- *"Compare the top and bottom store by month-to-date sales."*
- *"What's the labor cost % by store, and where is it highest?"*
- A **what-if**: *"If foot traffic rises 15% next week, which stores are most
  understaffed?"*
Cue: *"This is embedded **Genie** — self-service natural-language analytics over the
same governed data, so the regional manager answers their own questions instead of
filing a ticket and waiting days."*

---

## Part 3 — TELL: recap & land the value (~2 min)

Zoom back out to the three capabilities from slide 2 and connect them to what they
just saw:
- **Unified Operations** — the live Operations view and the fleet map replaced
  "yesterday's reports" with a real-time 360°, right down to live weather + events.
- **Forward-Looking Planning** — Forecast → Labor → Inventory → Kitchen Prep turned
  guesswork into a predict-recommend-**act** loop, writing decisions back to
  Lakebase.
- **Decision Intelligence** — Genie answered the "why" and the "what-if" in
  seconds, with no BI ticket.

Close on the platform story: *"Every piece of this — the governed data, the ML, the
operational writes, the natural-language layer, and the app itself — is one system
built natively on Databricks. Built once, and deployable for any multi-site
operator like you."* Then hand off to next steps (a scoped pilot on their data,
an architecture deep-dive, etc.).

---

## Cues & tips
- **Keep the arc visible:** each SHOW tab is one of the three promised capabilities
  — say which one as you open it, so the recap writes itself.
- **Trim to time:** the must-hits are Operations, Forecast, and Genie. Labor /
  Inventory / Kitchen Prep can be a fast montage if you're short.
- **Make it real:** actually place an order / approve a schedule so they see the
  **write-back to Lakebase** — that's what separates a dashboard from a system of action.
- **Localize:** if it's a real prospect, mention the demo can be re-skinned to their
  brand, stores, and menu in an afternoon (that's what this accelerator does).
- **Data caveat:** the data is synthetic and the fleet is a reference set; the
  weather and events, however, are live. Say so if asked.
