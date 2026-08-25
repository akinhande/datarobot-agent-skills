---
name: datarobot-llm-gateway
description: >-
  Use when the user wants to configure LLM integration for a DataRobot agent
  application. This skill helps to change LLM model, switch between the LLM
  integrations the project supports (LLM Gateway, a DataRobot-deployed LLM, an
  external provider, an LLM Blueprint, and any others its config declares), or
  set up provider credentials. The skill reads the project's
  .datarobot/cli/llm.yml for the real options, interviews the user, then runs
  sync_llm_env.py with the chosen values as CLI args to merge into .env.
---

# DataRobot LLM gateway configuration

Configure LLM integration **without hand-editing `.env`**. The skill drives
`sync_llm_env.py` with the user's answers as CLI arguments.

## Resolve script path once per session

`<skill_scripts_dir>` = the `scripts/` subdirectory of the directory containing this `SKILL.md`.

```shell
ls <skill_scripts_dir>/sync_llm_env.py
```

## Hard rules

1. **Never** ask the user to paste API keys or `DATAROBOT_API_TOKEN` in chat
2. **Never** read, copy, echo, or pass `DATAROBOT_API_TOKEN` yourself. The
   token lives in `$XDG_CONFIG_HOME/datarobot/drconfig.yaml` (default
   `~/.config/datarobot/drconfig.yaml`), populated by `dr auth login`, and
   the `dr` CLI reads it internally. Do not run `cat drconfig.yaml`,
   `cat .env`, `env | grep TOKEN`, `echo $DATAROBOT_API_TOKEN`,
   `curl -H "Authorization: Bearer $..."`, or any equivalent one-liner
3. **Never** pass secrets as CLI args to `sync_llm_env.py` or write them to
   tracked files
4. **Never** set provider credentials for an integration whose config section
   doesn't declare them. Let `sync_llm_env.py` decide — it reads the section
   from the project's config
5. Only `sync_llm_env.py` merges LLM keys into `.env` — do not edit `.env` manually
6. Run all commands from **project root**
7. Pressing enter in chat does nothing. Don't tell the user to "press enter to
   accept the default" or "hit return". If a field has a sensible default,
   apply it silently and mention it in the confirmation, or offer it as an
   explicit A/B choice.
8. Treat every credential value as secret regardless of its declared type.
   Older configs type API keys as plain `string` rather than `secret_string`,
   so this rule does not depend on what the config says

---

## Step 0 — Prerequisites

1. `.datarobot/cli/llm.yml` must be present. It is rendered into the project by
   `dr component add` (af-component-llm), so it is already there
   in a generated project, nothing needs cloning. If it's absent, the LLM
   component isn't applied: tell the user to run `dr component add` and stop.
   Never substitute a copy from elsewhere.
2. **DataRobot auth** — check that
   `$XDG_CONFIG_HOME/datarobot/drconfig.yaml` (default
   `~/.config/datarobot/drconfig.yaml`) exists. If it doesn't, tell the user
   to run `dr auth login` (browser-based flow) and stop until they confirm
   they're signed in. Do **not** cat the file to inspect its contents.
3. Check if `.env` exist in the project:
   - If `.env` is missing `cp .env.template .env`. That gives the base variables (`DATAROBOT_*`,
     `PULUMI_*`, etc.) many are blank, it will be filled later. But the sync in Step 3
     only needs the file to exist.
   - If both `.env` and no `.env.template` are missing, tell the user they're not in
     a DataRobot agent project root and stop.

---

## Step 1 — Read the project's integration options (MANDATORY FIRST)

Never recite integration names from memory or from this file. Each project's
`.datarobot/cli/llm.yml` declares its own, and they differ by component version.

```shell
python <skill_scripts_dir>/read_llm_config.py
```
If it reports the file is missing, the LLM component isn't applied to this
project. Tell the user to run `dr component add` and stop.
Do **not** run `dr llm-gateway list`, do **not** offer a model list, and do
**not** write any config file until the user has picked an option.
Print the `help` text it returns verbatim, then one lettered row per option,
using each `name` exactly as printed. Count the options; print exactly that
many rows. Do not rename, regroup, reorder, add a catch-all row, or end with
`...`.
Every row prints a `select:` field, like this:
```
  LLM Gateway  |  select: gateway_direct.py  |  requires: llm_gateway
```
Wait for the user's letter, then carry that row's `select:` string forward
verbatim — quote it if it contains spaces. The steps below call it
`<selected_gateway>`; it is also the `INFRA_ENABLE_LLM` value written in Step 3.
---

## Step 2 — Read what that option needs

```shell
python <skill_scripts_dir>/read_llm_config.py --option <selected_gateway>
```

This prints the env vars the chosen integration declares. Handle each field by
what the script reports about it:

- **`hidden`** — never ask. Step 3 writes its default.
- **`llmgw_catalog`** — populate from the DataRobot CLI (see below).
- **`required`** — ask, using the printed help as the prompt text.
- **`optional` with a default** — apply it silently and say so in the
  confirmation. Do not tell the user to "press enter".
- **`further choice:`** — present as another lettered menu. Those rows carry
  their own `select:` field; call the user's pick `<selected_provider>` and
  re-run `--option <selected_provider>` to get its keys.

### Fields typed `llmgw_catalog`

Fetch the model list **only** via the DataRobot CLI. Run exactly:

```shell
dr llm-gateway list --output-format json
```

The CLI authenticates via its own credential store (populated by
`dr auth login`). Do **not** read `drconfig.yaml` or `.env` for the token, and
do **not** pass `DATAROBOT_API_TOKEN` on the command line. If the command exits
non-zero or prompts for auth, tell the user to run `dr auth login` and stop —
do not attempt any manual API call and do not fabricate a menu.

Parse the JSON, which has the shape
`{"llms": [{"id", "name", "provider", "model", "selected"}, ...]}`. Use the
`model` field for each entry. The ids in the menu **must** come from that JSON,
verbatim, in the order returned. Do not invent ids or reuse them from your
training data. If the command did not produce JSON, stop and report the error.

Count the entries; call it `N`. Print **exactly `N` labelled lines**, one per
model. The letter scheme is `A..Z`, then `AA..AZ`, `BA..BZ`, and so on.

**Forbidden shortcuts** — none of these are acceptable:
- Ending the list with `...`, `…`, or "and N more"
- A catch-all row like `E) other`, `F) other`, `Z) other model`
- "I'll skip the rest for brevity"
- Summarization, grouping-family collapse, or "similar variants omitted"
- Rendering fewer than `N` rows and telling the user to ask if they want more

Long output is fine; the token budget for this message is not a reason to
abbreviate. `sync_llm_env.py` prepends `datarobot/` for this field type, so
pass the id exactly as the CLI returned it.

### Credential keys

**Announce them up front** — do not let the user discover them via the sync
error message. Once the further choice is made, re-run
`--option <selected_provider>` and
tell the user exactly which keys they need and where the file lives:
```
For <choice>, I'll need these values in a per-user credentials file:
  ~/.config/datarobot/llm-<section>.env (or $XDG_CONFIG_HOME/...)

  <KEY_1>
  <KEY_2>
  ...
Step 3 will create that file as a blank template, with the help text for
each key as a comment, if it doesn't exist. Please fill it in your own
editor — do not paste the values in chat — then tell me "credentials ready"
and I'll re-run the sync.
```
Use the section name the script reported for `<section>`. Do not create the
file yourself, do not `cat` it, and do not accept secret values in chat.
---

## Step 3 — Sync into `.env`

Run the sync script with the values collected in Step 2 as CLI args. No
intermediate config file, no JSON to write.

```shell
python <skill_scripts_dir>/sync_llm_env.py \
  --infra-enable-llm <selected_gateway> \
  --set <ENV_NAME>=<value>
```
Repeat `--set` once per value, using the env var names the script printed in
Step 2 — they carry a per-project prefix and are **not** always `LLM_*`. Add
`--provider "<selected_provider>"` when Step 2 reported a further choice. Pass no
`--set` for fields reported as `hidden`; the script writes their defaults.
When the chosen option needs credentials, the script reads them from
`$XDG_CONFIG_HOME/datarobot/llm-<section>.env`:
- **If the file doesn't exist**, the script writes a blank template there
  and exits with the path plus the required key list. Relay that verbatim
  to the user, tell them to fill it in their own editor, then re-run the
  same command. Do not offer to create the file for them and do not accept
  values in chat.
- **If the file exists but is incomplete**, the script prints the missing
  keys and exits. Same instruction: user edits, then re-runs.
- **If the file is complete**, the sync merges the credentials into `.env`
  in one shot.
---

## Step 4 — Validate and hand off

**`dr dotenv validate` echoes the full `.env` (including `DATAROBOT_API_TOKEN`)
to stdout.** If you run it without redirection, the token lands in the chat
transcript and must be rotated. Same risk for `dr dotenv update`, `dr task run`,
`dr run`, `cat .env`, `env | grep`, or any other command that reads `.env`.

Run validation with all output suppressed and check only the exit code:

```shell
dr dotenv validate >/dev/null 2>&1
```

- **Exit 0** → tell the user validation passed.
- **Non-zero exit** → do **not** re-run the command with output visible.
  Tell the user to run `dr dotenv validate` themselves in their own terminal
  so the error stays local.
Then tell the user (do not run these yourself — they also echo secrets):
```text
LLM configuration synced to .env.

Please run these yourself in your terminal:
  dr dotenv update          # refresh DataRobot token if needed
  dr task run infra:up-yes  # push runtime params to deployment
  dr run dev                # local test
```
---

## Stale keys

`sync_llm_env.py` derives its managed-key set from every env var declared
anywhere in the project's config, so switching integrations clears whatever the
previous one wrote before the fresh block goes in. Non-LLM `.env` lines are
preserved.
