# DataRobot Agent Application — Custom MCP Tool Workflow

Author and deploy a custom MCP tool inside the **DataRobot agent application template** (the agentic starter app). The agent connects to its bundled MCP server over HTTP via the `mcp_tools` function group — adding a tool there automatically exposes it to the agent, with no per-tool registration in `workflow.yaml`.

> **Secrets handling.** The rules in `SKILL.md` § *Secrets handling* govern every command in this file. Never echo, cat, log, or otherwise print `DATAROBOT_API_TOKEN`, `.env` contents, or any other secret. When a command needs the token, use the shell variable `$DATAROBOT_API_TOKEN`; do not substitute the literal value.

## Workflow checklist

Copy and track progress:

```text
- [ ] 1. Run `dr task run mcp_server:install` from the project root (only if deps changed)
- [ ] 2. Create or edit a file in `mcp_server/app/tools/` with an `@dr_mcp_tool` async function
- [ ] 3. Import the module from `mcp_server/app/tools/__init__.py` (only if new file)
- [ ] 4. Restart `dr task dev` — verify the tool appears in MCP `tools/list`
- [ ] 5. (Optional) Update `agent/workflow.yaml` `system_prompt` so the agent knows when to call it
- [ ] 6. (Optional) Deploy via `dr task run infra:up-yes` — the MCP server ships with the agent
```

## Overview

Custom MCP tools live in the **MCP server** (`mcp_server/`), not in the agent Python code. The agent connects to them over HTTP via the MCP protocol.

```text
User → Agent → MCP Server → Your Custom Tool → (optional) External API / DataRobot API
```

The agent is already wired for MCP in `agent/workflow.yaml` via the `mcp_tools` function group. You do **not** register each custom tool individually — once the MCP server exposes a tool, the agent discovers and can call it automatically.

## Step-by-step

### Step 1: Install MCP server dependencies

From the **project root**:

```shell
dr task run mcp_server:install
```

Run this again whenever you add new Python packages to `mcp_server/pyproject.toml`.

### Step 2: Create your tool file

Add a new file under `mcp_server/app/tools/`, for example `mcp_server/app/tools/my_tools.py`.

**Requirements:**

- Function must be `async def`
- Decorate with `@dr_mcp_tool(...)` — this registers the tool
- Parameters use `Annotated[type, "description"]`
- Return `ToolResult(structured_content={...})`
- Raise `ToolError` for validation errors

**Example:**

```python
# mcp_server/app/tools/my_tools.py
from typing import Annotated

from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult


@dr_mcp_tool(tags={"custom", "greeting"})
async def greet_user(
    name: Annotated[str, "The person's name to greet."],
) -> ToolResult:
    """
    Return a friendly greeting for the given name.
    Use this when the user asks to be greeted by name.
    """
    if not name or not name.strip():
        raise ToolError("name cannot be empty.")

    return ToolResult(
        structured_content={
            "greeting": f"Hello, {name.strip()}!",
        }
    )
```

A starter template may exist in `mcp_server/app/tools/user_tools.py`. The `@dr_mcp_tool` decorator is commented out by default — uncomment it to enable the example tool.

**Example using the DataRobot API:**

```python
# mcp_server/app/tools/my_custom_tool.py
from typing import Annotated

import datarobot as dr
from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult


@dr_mcp_tool(tags={"custom", "example"})
async def my_custom_tool(
    input_param: Annotated[str, "A required input string."],
    optional_param: Annotated[int, "Optional integer parameter."] = 10,
) -> ToolResult:
    """
    Example custom tool.

    Keep the description specific so the LLM can decide when to use the tool.
    """
    if not input_param.strip():
        raise ToolError("input_param cannot be empty.")

    # Example DataRobot API call.
    _ = dr.Project.list()

    return ToolResult(
        structured_content={
            "message": f"Processed {input_param!r} with {optional_param}"
        }
    )
```

**Important rules:**

- Only modify files inside `mcp_server/`
- Do **not** import code from `agent/` or `fastapi_server/` — the MCP server has independent dependencies
- Write a clear docstring — the LLM uses it to decide when to call the tool

### Step 3: Ensure the module is loaded

The server loads modules from `mcp_server/app/tools/` at startup via `app/main.py`:

```python
additional_module_paths=[
    (os.path.join(app_dir, "tools"), "app.tools"),
    ...
],
```

If you create a **new** Python file, import it from `mcp_server/app/tools/__init__.py` so the `@dr_mcp_tool` decorator runs when the server starts:

```python
from app.tools import my_tools  # noqa: F401
```

#### If your tool needs secrets or configuration

1. Add fields to `mcp_server/app/core/user_config.py` (`UserAppConfig`)
2. Read them with `get_user_config()` inside your tool
3. Add values to `.env` (never hardcode secrets in tool code)

Example:

```python
from app.core.user_config import get_user_config

config = get_user_config()
# use config.your_field
```

See `docs/mcp-server.md` in the agent application repo for the full configuration reference.

### Step 4: Verify locally with dev mode

Start the dev server from the project root:

```shell
dr task dev
```

Once it's running, list the MCP server's tools at the local MCP endpoint printed in the dev output (typically `http://localhost:8080/mcp/`) and confirm your new tool appears in `tools/list`. If it doesn't, see Troubleshooting.

### Step 5: Agent configuration

Your `agent/workflow.yaml` already includes MCP wiring:

```yaml
function_groups:
  mcp_tools:
    _type: datarobot_mcp_client

authentication:
  datarobot_mcp_auth:
    _type: datarobot_mcp_auth

workflow:
  tool_names:
    - mcp_tools
```

You do **not** add each MCP tool name to `workflow.yaml`. The `mcp_tools` group discovers all tools from the MCP server dynamically.

**Optional:** Update `workflow.system_prompt` so the agent knows when to use your new tool (for example, "Use `greet_user` when the user asks for a personalized greeting").

When you deploy with `dr task run infra:up-yes`, the MCP server in your project is deployed with your custom tools. **The deployed in-project MCP server takes precedence over `MCP_DEPLOYMENT_ID` / `EXTERNAL_MCP_URL` test overrides** — unset those env vars if you intended to call the in-project MCP server.

## Tool best practices

- Use clear docstrings so the LLM can understand the tool's purpose.
- Add type hints for every parameter and the return value.
- Use `Annotated[...]` to provide short, helpful parameter descriptions.
- Raise `ToolError` for validation failures or expected runtime errors.
- Return structured results when possible so downstream consumers can parse them easily.
- Use descriptive tags to group related tools.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Tool not in MCP `tools/list` after restart | Confirm `@dr_mcp_tool` is uncommented; ensure the file is imported from `mcp_server/app/tools/__init__.py`; restart `dr task dev` |
| Import error on startup | Re-run `dr task run mcp_server:install` if you added Python deps to `mcp_server/pyproject.toml` |
| Agent hits an external MCP, not yours | Unset `MCP_DEPLOYMENT_ID` and `EXTERNAL_MCP_URL` — deployed in-project MCP usually takes precedence, but test overrides can leak |
| Config field returns `None` | Field added to `UserAppConfig` but `.env` value missing; restart `dr task dev` after editing `.env` |

## Related documentation (in the agent application repo)

- `docs/mcp-server.md` — how the application connects to MCP locally and in deployment
- `mcp_server/AGENTS.md` (if present) — additional rules for editing the MCP server
- `agent/workflow.yaml` — the agent's function groups and authentication config
