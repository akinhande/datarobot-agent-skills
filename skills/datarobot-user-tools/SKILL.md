---
name: datarobot-user-tools
description: Use when scaffolding, adding, configuring, testing, or deploying a custom MCP tool inside a DataRobot agent or MCP repo (e.g., datarobot-agent-application, datarobot-mcp-template). Triggers include "custom MCP tool", "add tool to agent", "dr_mcp_tool", "mcp_server tools", "user MCP", "dr component setup", "scaffold a new agent/MCP repo", or extending an agentic/MCP starter app with a new tool function.
---

# DataRobot Custom MCP Tool Skill

Walk through creating, testing, and deploying a custom MCP tool across multiple DataRobot starter repositories. The detailed per-repo workflow lives in `references/`; this file routes to the right one so each repository's specifics stay authoritative.

## Secrets handling (must read)

These rules apply to every command this skill runs or suggests:

- **Never** `echo`, `printf`, `cat`, `head`, `tail`, `grep`, or otherwise print the value of `DATAROBOT_API_TOKEN` (or any other token, password, key, or secret). Treat them as write-only.
- **Never** print the contents of a `.env`, `.envrc`, `drconfig.yaml`, or similar credential file. Use existence checks (`test -f <path> && echo "found" || echo "missing"`) only.
- When a command needs the token, reference it as `$DATAROBOT_API_TOKEN` so the shell expands it at execution. Do **not** substitute the literal token string into the command, chat, or any file the user can see.
- Do not pipe credential files into other commands, copy them to clipboards, or write them into prompts, log lines, or tool output.
- If credentials are missing or invalid, invoke the `datarobot-setup` skill — do not inline credential-setup steps or prompt the user to paste secrets here.
- If you cannot verify something without exposing a secret, stop and ask the user instead.

## When to use this skill

Use this skill when the user needs to:

- Add a new custom MCP tool to an existing DataRobot agent application or user MCP server with MCP template.
- Expose a DataRobot API call or external service as an MCP tool.
- Add configuration for a custom tool, or update existing custom tool.
- Test or deploy a custom MCP tool alongside an agent or as a standalone user MCP.

## Step 1: Confirm scope (local-only vs deploy)

Before doing any work, ask the user once whether this run should stop after a local check or also deploy. The two paths diverge — only deploy needs `pulumi` (for the MCP template repo) and a fully working DataRobot deployment environment.

If the user has not already stated intent in the conversation, ask:

> "Once I add this tool, do you want me to:
> - **(a) local only** — add the tool, run lint/tests, and verify it locally; you'll deploy later, or
> - **(b) add + deploy** — also deploy so it's reachable from your DataRobot MCP endpoint?"

Echo their choice back in one sentence before continuing. Carry the choice through the rest of the workflow:

| Scope | datarobot-agent-application | datarobot-mcp-template |
|---|---|---|
| **(a) local only** | Run checklist items 1–4; stop before `dr task run infra:up-yes` | Run checklist items 1–5; stop before `task deploy` |
| **(b) add + deploy** | Run the full checklist through `dr task run infra:up-yes` | Run the full checklist through `task deploy` and the curl `tools/list` verify |

If the user explicitly asked for one path in their request ("just add a tool" → local only; "deploy a new tool" → deploy), skip the question and confirm the inferred choice in one sentence.

## Step 2: Pre-flight check

Confirm the toolchain before scaffolding or touching a repo, since `dr component setup` and the rest of the workflow both rely on the DataRobot CLI. Record each result and skip install steps in the reference whose check already passes. **Skip the `pulumi` check if the user chose (a) local-only.** Skip credential checks only if the user chose local-only *and* already has a `dr task dev` session running without auth errors.

```bash
command -v python3 && python3 --version
command -v uv && uv --version
command -v dr && dr --version
command -v task && task --version
command -v pulumi && pulumi version    # required only for datarobot-mcp-template + deploy
python3 -c "import datarobot; print(datarobot.__version__)" 2>/dev/null

# Credential presence checks — these only print "set" or "missing", never the value.
# Do not replace these with commands that could surface the token (no echo $VAR, no cat .env).
[ -n "${DATAROBOT_API_TOKEN-}" ] && echo "DATAROBOT_API_TOKEN: set" || echo "DATAROBOT_API_TOKEN: missing"
[ -n "${DATAROBOT_ENDPOINT-}"  ] && echo "DATAROBOT_ENDPOINT: set"  || echo "DATAROBOT_ENDPOINT: missing"
test -f ~/.config/datarobot/drconfig.yaml && echo "drconfig: found" || echo "drconfig: missing"
```

If any DataRobot credential or CLI is missing or invalid, invoke the `datarobot-setup` skill and then resume here. Do not print manual setup instructions inline.

## Step 3: Locate or scaffold the target repository

First ask whether the user is working in an existing repo or needs to scaffold a new one:

> "Do you already have a DataRobot agent or MCP repo for this tool, or should I scaffold a new one with `dr component setup`?"

Skip the question if the user's request already makes the answer obvious (e.g., "add a tool to my existing agent app" → existing; "set up a new MCP template and add a tool" → scaffold).

### Path A: Scaffold a new repo

Ask for the parent directory where the new repo should live (e.g., `~/workspace`), then run `dr component setup` from there so its interactive picker opens. Tell the user which option to choose based on intent:

| User wants… | Pick in `dr component setup` |
|---|---|
| Agent app with a bundled MCP server | `datarobot-agent-application` |
| Standalone user MCP server | `datarobot-mcp-template` |

```bash
cd <parent-dir>
dr component setup
```

After scaffold completes, `cd` into the newly created repo directory and continue to Step 4.

### Path B: Use an existing repo

Check the current working directory for a known layout:

```bash
pwd
test -d mcp_server/app/tools && echo "agent-application layout"
test -d dr_mcp/app/tools && echo "mcp-template layout"
```

| Layout hint | Reference to follow |
|---|---|
| `mcp_server/app/tools/`, `agent/workflow.yaml` | `references/datarobot-agent-application.md` |
| `dr_mcp/app/tools/`, `infra/`, `dev_tools/lineage/` | `references/datarobot-mcp-template.md` |

If neither layout matches the current directory, ask:

> "Where is your project located? (e.g., `~/workspace/datarobot-agent-application`)"

Then `cd` into that repo before doing any work.

## Step 4: Execute the matching workflow

Open the reference for the detected repository and follow it step by step, stopping at the boundary set in Step 1. Read it fresh each time — do not summarize from memory, and do not duplicate its content here:

- **Agent application** → `references/datarobot-agent-application.md`
  - Tools live in `mcp_server/app/tools/`
  - Local restart of `dr task dev` picks up new tools automatically via the `mcp_tools` function group
  - Deployed alongside the agent via `dr task run infra:up-yes`; no separate MCP deploy

- **MCP template** → `references/datarobot-mcp-template.md`
  - Tools live in `dr_mcp/app/tools/`
  - Lineage metadata must be regenerated (`task install`) before deploy
  - Deployed as a standalone user MCP via `task deploy`; updates reuse the existing Pulumi stack (`pulumi stack select`, never `stack init` or `task destroy` for tool-only changes)
  - Tools are discovered by the global MCP proxy after the user MCP starts and runs lineage sync

## Tool authoring rules (both repos)

These constraints apply regardless of which repo you are in. The per-repo reference covers everything else.

- Function is `async def` and decorated with `@dr_mcp_tool(tags={...})`
- Parameters use `Annotated[type, "description"]` so the LLM sees a short hint per arg
- Returns `ToolResult(structured_content={...})`
- Raises `ToolError` for validation failures or expected runtime errors
- Modify code only inside the MCP server directory of the repo (`mcp_server/` or `dr_mcp/`); never import from agent or app code outside it
- Write a clear docstring — the LLM uses it to decide when to call the tool
- Never hardcode secrets; use `get_user_config()` or environment variables

## Reporting back

When the workflow finishes, tell the user:

1. Which tool(s) were added and where (file path, tool name)
2. Scope that ran — local-only or deploy
3. Verification result — tool appears in `tools/list` (via local server for local-only, via `curl` against the deployed endpoint for deploy)
4. If deployed: deployment ID and MCP endpoint, noting whether the endpoint changed
5. If local-only: a one-line reminder of how to deploy later (`dr task run infra:up-yes` or `task deploy`, depending on repo)

Do not commit changes or push branches unless the user explicitly asks. 
