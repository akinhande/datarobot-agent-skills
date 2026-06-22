# DataRobot User MCP Tools

Guide users through authoring custom tools in this repo's **user MCP** (`dr_mcp/`) and deploying them so they are discoverable and callable via DataRobot's **global MCP** proxy.

> **Secrets handling.** The rules in `SKILL.md` § *Secrets handling* govern every command in this file. Never echo, cat, log, or otherwise print `DATAROBOT_API_TOKEN`, `.env` contents, or any other secret. When a command needs the token, use the shell variable `$DATAROBOT_API_TOKEN`; do not substitute the literal value.

## Workflow checklist

Copy and track progress:

```text
- [ ] 1. Create or edit tool in dr_mcp/app/tools/
- [ ] 2. Add @dr_mcp_tool decorator and ToolResult return
- [ ] 3. Run lint + tests in dr_mcp/
- [ ] 4. Test locally (task dev / test-interactive)
- [ ] 5. Regenerate lineage metadata (task install)
- [ ] 6. Deploy or update user MCP (task deploy — see § Updating existing deployment)
- [ ] 7. Verify tool appears in `tools/list` via curl against the deployed MCP endpoint
```

---

## Step 1: Create a custom tool

Before editing, skim `dr_mcp/AGENTS.md` and `docs/datarobot-mcp/custom_tools.md` — those are the authoritative authoring docs for this template.

Add a new file under `dr_mcp/app/tools/` (e.g. `my_domain_tools.py`) or extend `user_tools.py`.

**Required pattern** — every tool must be `async def` and return `ToolResult`:

```python
from typing import Annotated

from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult


@dr_mcp_tool(tags={"domain", "action"})
async def my_custom_tool(
    input_param: Annotated[str, "Short description the LLM will see."],
) -> ToolResult:
    """Clear docstring explaining when the LLM should call this tool."""

    if not input_param.strip():
        raise ToolError("input_param cannot be empty.")

    return ToolResult(
        structured_content={"message": f"Processed {input_param!r}"}
    )
```

**Rules**

| Requirement | Detail |
|---|---|
| Decorator | `@dr_mcp_tool(tags={...})` — uncomment it; example in `user_tools.py` is commented out by default |
| Parameters | `Annotated[type, "description"]` on every parameter |
| Errors | Raise `ToolError` for validation / expected failures |
| Return | `ToolResult(structured_content={...})` |
| Registration | None — auto-discovered from `app/tools/` on startup |
| Secrets | Never hardcode; use env vars or runtime params via `get_user_config()` |

**Optional config** — if the tool needs deploy-time settings:

1. Add runtime param in `infra/infra/dr_mcp_user_params.py`
2. Add matching field in `dr_mcp/app/core/user_config.py`
3. Read with `get_user_config()` inside the tool

### Examples

#### Minimal tool (copy-paste starter)

```python
# dr_mcp/app/tools/greeting_tools.py
from typing import Annotated

from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult


@dr_mcp_tool(tags={"greeting", "example"})
async def greet_user(
    name: Annotated[str, "Name of the person to greet."],
) -> ToolResult:
    """Return a greeting for the given name."""

    if not name.strip():
        raise ToolError("name cannot be empty.")

    return ToolResult(structured_content={"greeting": f"Hello, {name}!"})
```

#### Tool using user config

```python
# dr_mcp/app/tools/configured_tools.py
from typing import Annotated

from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.tools.tool import ToolResult

from app.core.user_config import get_user_config


@dr_mcp_tool(tags={"config", "example"})
async def who_am_i(
    _: Annotated[str, "Unused; call with any string."] = "",
) -> ToolResult:
    """Return the configured user_name from deployment runtime parameters."""

    config = get_user_config()
    return ToolResult(structured_content={"user_name": config.user_name})
```

Matching infra (`infra/infra/dr_mcp_user_params.py`):

```python
pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
    key="user_name",
    type="string",
    value=os.getenv("USER_NAME", "default-user"),
),
```

#### Enabling the template example tool

In `dr_mcp/app/tools/user_tools.py`, uncomment the decorator:

```python
@dr_mcp_tool(tags={"user", "tools", "example"})
async def user_tool_example(...):
```

Then unskip `dr_mcp/app/tests/integration/test_user_tools.py`.

#### Integration test snippet

```python
import pytest
from datarobot_genai.drmcp import integration_test_mcp_session
from mcp.types import CallToolResult, ListToolsResult


@pytest.mark.asyncio
async def test_greet_user() -> None:
    async with integration_test_mcp_session() as session:
        tools = await session.list_tools()
        assert "greet_user" in [t.name for t in tools.tools]

        result: CallToolResult = await session.call_tool(
            "greet_user", {"name": "Ada"}
        )
        assert not result.isError
```

---

## Step 2: Test locally

From `dr_mcp/`:

```bash
# .env must include DATAROBOT_API_TOKEN, DATAROBOT_ENDPOINT, SESSION_SECRET_KEY
task dev                  # http://localhost:8080/mcp/
task test-interactive     # optional agent smoke test
task lint
task test
```

**Integration test** — add or unskip tests in `dr_mcp/app/tests/integration/`. The sample `test_user_tools.py` is skipped until `@dr_mcp_tool` is enabled.

---

## Step 3: Regenerate lineage metadata

On `task install`, the lineage CLI introspects registered tools and writes YAML:

```text
dr_mcp/dev_tools/lineage/mcp_item_metadata/
├── mcp_tools.yaml
├── mcp_prompts.yaml
└── mcp_resources.yaml
```

Run explicitly after adding tools:

```bash
cd dr_mcp
task install
# or: uv run dev_tools/lineage/cli.py load-and-save-mcp-item-metadata
```

This metadata is how DataRobot links user tool definitions to the deployed MCP server version. Lineage sync also runs on user MCP startup in production.

---

## Step 4: Deploy the user MCP to DataRobot

From the **repo root**. Ensure `dr_mcp/.env` and root `.env` are configured (see [README.md](../../../README.md#configure-environment-variables)):

```bash
pulumi login --local         # or a shared backend
task deploy                  # install + infra:deploy → pulumi up
```

**What gets deployed** (`infra/infra/dr_mcp.py`):

1. Execution environment (default: `[DataRobot] Python 3.11 GenAI Agents`)
2. Custom model packaging `dr_mcp/app/`, `pyproject.toml`, `uv.lock`
3. Registered model + serverless deployment
4. `UserMcpToolMetadata` Pulumi resources from lineage YAML

**Post-deploy outputs**

- Custom model ID and deployment ID — record these for follow-up updates; Step 5's curl substitutes the deployment ID into the MCP endpoint URL.
- Tool metadata count — must increase by one (or more) when you add new tools; if it doesn't, the new tool wasn't registered.

```bash
task infra:info              # check stack status and tool metadata count
```

---

## Updating an existing deployment (new tools)

Use this when the user **already has a deployed user MCP** (and optionally an agent on the **global MCP**) and only needs to **add or change custom tools** — not a greenfield deploy.

### What happens on update

| Resource | On `task deploy` (pulumi up) |
|---|---|
| Custom model | New **version** with updated `dr_mcp/app/` code |
| Registered model | New version pointing at the new custom model version |
| Deployment | **Updated in place** — same deployment ID in most cases |
| MCP endpoint URL | Usually **unchanged** (`.../deployments/<id>/directAccess/mcp/`) |
| Lineage (`UserMcpToolMetadata`) | New/updated records from regenerated `mcp_tools.yaml` |
| Global MCP catalog | Picks up new tools after deploy + user MCP startup lineage sync |

**Do not** run `task destroy` or `pulumi stack init` for a routine tool update.

### Update workflow

```text
1. Add/change tools in dr_mcp/app/tools/
2. cd dr_mcp && task lint && task test
3. cd dr_mcp && task install          # REQUIRED — refreshes mcp_tools.yaml
4. Confirm new tool name in dr_mcp/dev_tools/lineage/mcp_item_metadata/mcp_tools.yaml
5. Select existing Pulumi stack (not init):
     cd infra && uv run pulumi stack select <existing-stack>
6. From repo root: task deploy        # pulumi up → new model version, redeploy
7. task infra:info                    # confirm deployment ID / endpoint unchanged
8. Verify tools/list on deployed endpoint with curl
```

```bash
# 1. Confirm current deployment (note deployment ID / MCP endpoint)
task infra:info

# 2. After tool changes + task install
cd infra && uv run pulumi stack select <your-existing-stack>
cd .. && task deploy

# 3. Verify new tool is registered
task infra:info   # check tool metadata count increased
```

### Asking the user (existing deployment)

If the user says they already have a deployed MCP or agent, ask only what you cannot infer from the repo:

```markdown
To update your existing MCP with the new tools, I need:

**Pulumi stack name** — the stack used for the original deploy  
(If unsure: run `cd infra && uv run pulumi stack ls` or check your team's docs.)

```

Lineage sync runs on **every user MCP startup** in production (see CHANGELOG). Redeploy rolls out a new server version; once healthy, the global MCP can discover and proxy the new tool names — typically same deployment URL when the deployment ID is unchanged.

### First deploy vs update

| Step | First deploy | Update existing |
|---|---|---|
| `pulumi stack init` | Yes | **No** — use `pulumi stack select` |
| `cp dr_mcp/.env .env` | Yes | Only if root `.env` missing |
| `task install` before deploy | Yes | **Yes** — required for lineage |
| MCP endpoint | New URL | Usually same URL |

---

## Step 5: Verify tools on the deployed MCP endpoint

After deploy, hit the deployed user MCP directly and confirm the new tool appears in `tools/list`. This is something the agent can run on its own; no MCP client UI required.

```bash
# The shell expands $DATAROBOT_API_TOKEN and $DATAROBOT_ENDPOINT at execution.
# Do NOT substitute the literal token value here, do not echo it, and do not paste it into chat or tool output.
curl -sS -X POST "$DATAROBOT_ENDPOINT/deployments/<deployment-id>/directAccess/mcp/" \
  -H "x-datarobot-api-key: $DATAROBOT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Confirm the new tool name appears in the response. If it does not, re-check `task install` ran (lineage `mcp_tools.yaml` updated) and that the deploy reported a new model version.

**Optional tool filtering** — the global MCP supports an `x-datarobot-mcp-tools` header to filter `tools/list` and `tools/call` by exact tool name.

---

## Agent implementation guide

When the user asks to create and deploy a custom tool, follow this order:

**If they already have a deployed user MCP**, use **Updating an existing deployment** (select existing stack, do not destroy).

1. **Clarify deploy mode** — first deploy vs update existing MCP/agent (ask for stack name if update).
2. **Read** `dr_mcp/AGENTS.md` and the target tool file(s) in `dr_mcp/app/tools/`.
3. **Implement** only inside `dr_mcp/` using the pattern above.
4. **Lint and test** — `cd dr_mcp && task lint && task test`.
5. **Regenerate metadata** — `cd dr_mcp && task install`; confirm new tool in `mcp_tools.yaml`.
6. **Deploy** — `cd infra && uv run pulumi stack select <stack>` then from repo root `task deploy`.
7. **Verify** new tool name(s) via `curl tools/list` against the deployed endpoint (see Step 5).
8. **Report** deployment ID, MCP endpoint (note if unchanged), and new tool name(s).

Do **not** commit `.env` or API tokens. Do **not** create git commits unless the user asks.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Tool not in `tools/list` locally | Ensure `@dr_mcp_tool` is uncommented; restart server |
| Tool missing after deploy | Re-run `task install` before `task deploy`; confirm tool is in `mcp_tools.yaml` |
| Tool missing in deployed `tools/list` after update | Confirm `task install` updated `mcp_tools.yaml`; confirm lineage metadata count in `task infra:info`; re-run `task deploy` if needed |
| Wrong deployment updated | Use `pulumi stack select` for correct stack; compare deployment ID before/after |
| Deploy fails on auth | Set `DATAROBOT_API_TOKEN` and `DATAROBOT_ENDPOINT` in root `.env` |
| Port in use locally | `export MCP_SERVER_PORT=8081` then `task dev` |
| Integration test skipped | Unskip `test_user_tools.py` after enabling the example tool |
| Missing `.env` / credentials | See `README.md` § Configure environment variables in the target repo, or invoke the `datarobot-setup` skill |

---

## Related docs

| Doc | Path |
|---|---|
| Custom tools guide | `docs/datarobot-mcp/custom_tools.md` |
| Server architecture | `docs/datarobot-mcp/mcp_server_architecture.md` |
| MCP client setup | `docs/datarobot-mcp/mcp_client_setup.md` |
| Dynamic tool registration | `docs/datarobot-mcp/dynamic_tool_registration.md` |
| Deployment README | `README.md` § Deployment |
