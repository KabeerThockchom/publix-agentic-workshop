# Zerobus Service Principal - one-time admin setup

The Zerobus publisher (Notebook 3 / `src/zerobus/publisher.py`) runs from a laptop and streams events
into the bronze tables. It authenticates as a **service principal (SP)** - a non-human identity - not
as a workshop participant.

Do this **once** before the workshop. Participants never create an SP; they only need their workspace
login. You (the workshop admin / instructor) provision one shared SP and share its credentials.

Why an SP and not a user login? Zerobus ingest is machine-to-machine (OAuth client credentials), which
is how streaming ingest runs in production. One shared SP keeps participant setup to "paste two values."

---

## Step 1 - Create the service principal

**UI:** Settings → Identity and access → **Service principals** → **Add service principal** →
name it `publix-zerobus-publisher` → Add.

**CLI (equivalent):**
```bash
databricks service-principals create --display-name publix-zerobus-publisher --profile <PROFILE>
```
Copy the **Application ID** (a UUID like `1b103dc1-...`). This is what participants grant in Notebook 1.

---

## Step 2 - Generate an OAuth secret for the SP

**UI:** open the SP → **Secrets** tab → **Generate secret** → set a lifetime → copy the **Secret** and the
**Client ID** (the Client ID equals the Application ID). You only see the secret once - copy it now.

This gives you two values:
- `client_id`  = the SP application id
- `client_secret` = the generated secret

---

## Step 3 - Store the credentials in a secret scope

So nothing is hard-coded or typed on screen, put the two values in a workspace secret scope:

```bash
databricks secrets create-scope publix_workshop --profile <PROFILE>
databricks secrets put-secret publix_workshop zerobus_client_id     --string-value "<application-id>" --profile <PROFILE>
databricks secrets put-secret publix_workshop zerobus_client_secret --string-value "<secret>"          --profile <PROFILE>
```

The publisher's env-var block (see `README.md`) reads these back.

---

## Step 4 - Grant the SP on the bronze tables

This happens **after** the schema and tables exist (it's baked into Notebook 1, Part 4).
Set `ZEROBUS_SP` to the application id from Step 1 and run that cell, or run this SQL directly (replacing `<yourname>` with your first name):

```sql
GRANT USE CATALOG ON CATALOG publix_technology TO `<application-id>`;
GRANT USE SCHEMA  ON SCHEMA  publix_technology.agentic_ai_training_<yourname> TO `<application-id>`;
GRANT SELECT, MODIFY ON SCHEMA publix_technology.agentic_ai_training_<yourname> TO `<application-id>`;
```

`MODIFY` = write (INSERT/UPDATE/DELETE). Without this grant the publisher fails with
`401 invalid_authorization_details`.

> Re-granting: if you **drop and recreate** the catalog, the grant is gone with it. Re-run Notebook 1
> Part 4 (or the SQL above) before the publisher will work again.

---

## Step 5 - What to hand participants

- The SP **application id** (for the Notebook 1 grant cell).
- The **Zerobus endpoint** and **workspace URL** (for their publisher env vars).
- Access to the `client_id` / `client_secret`: either grant them **READ** on the `publix_workshop`
  secret scope, or hand them the two values directly (throwaway workshop SP, so either is fine).

If only the instructor runs the publisher (demo, not hands-on), participants need none of the
credentials - they just watch the bronze tables fill.

---

## Alternative (not used here): run as your own user

The Zerobus Python SDK's `create_stream(..., headers_provider=...)` argument lets you supply custom auth
headers - e.g. a user Bearer token instead of SP client credentials. In principle a participant who
owns the catalog they created could publish as themselves with no SP.

We do **not** use this in the workshop: it needs a publisher code change and it's the SDK's
"custom authentication" escape hatch (less-tested for Zerobus ingest than the SP path). The shared SP
above is the tested, baby-steps path. Noted here only so you know the option exists.
