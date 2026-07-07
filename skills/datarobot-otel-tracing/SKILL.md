---
name: datarobot-otel-tracing
description: >-
  Use when the user wants to add DataRobot OpenTelemetry (OTel) tracing to an existing agentic
  project so its runs, LLM calls, and tool invocations show up in the DataRobot Tracing table.
  Triggers include "configure tracing", "add DataRobot tracing / observability", "send traces to
  DataRobot", "instrument my agent for DataRobot", or wiring up OTLP export to DataRobot — for a
  CrewAI, LangGraph/LangChain, or LlamaIndex codebase. This is specifically for projects that were
  NOT generated from the datarobot-agent-templates / datarobot-agent-application starter (a custom
  or pre-existing repo). Trigger it even if the user only names their framework and DataRobot
  without saying the word "OpenTelemetry", since the DataRobot integration is OTel under the hood.
---

# Configure DataRobot OpenTelemetry tracing

Wire DataRobot OTel tracing into an **existing** agent project (CrewAI, LangGraph/LangChain, or
LlamaIndex) that was not scaffolded from a DataRobot starter template. (If the user is willing to
adopt the DataRobot agent templates instead, that scaffolds tracing for them and this skill isn't
needed.) When done, the agent exports spans to DataRobot's OTLP collector and its runs appear in the
deployment **Tracing** table with Cost, Prompt, Completion, and Tools columns populated.

This assumes standard OpenTelemetry knowledge (creating a `TracerProvider`, exporters, spans,
attributes). It only spells out the parts specific to DataRobot; for the general OTel bits, use the
[OpenTelemetry Python docs](https://opentelemetry.io/docs/languages/python/).

## Prerequisites

`DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` must be set — run `datarobot-setup` if not.

The third value, `DATAROBOT_ENTITY_ID`, is skill-specific and the one most likely to be missing.
It identifies the resource the traces attach to, in the form `<entity_type>-<entity_id>` (e.g.
`deployment-abc123`). A blank or invalid value causes a **401** at export — it's part of collector
authorization, not just a label. Ask the user which entity (deployment / custom model /
application) the traces should attach to; if they can't provide one, tell them tracing stays
disabled until they do. You don't need a deployment to *emit* traces, but the entity id must
reference a resource that exists in DataRobot for the traces to be viewable there.

## Step 1 — Identify the framework and entry point

- **CrewAI** — `from crewai import ...`, `Crew(...)`, `crew.kickoff(...)` → `references/crewai.md`
- **LangGraph / LangChain** — `langgraph`, `StateGraph`, `graph.invoke(...)`, or plain `langchain`
  (instrumented with the LangChain instrumentor) → `references/langgraph.md`
- **LlamaIndex** — `llama_index`, `VectorStoreIndex`, `query_engine.query(...)` → `references/llamaindex.md`
- **None of these** (plain/custom agent) — skip the framework instrumentor, keep everything else,
  and instrument key steps with manual spans (Step 6).

The entry point is wherever the agent is kicked off (a `main()`, route handler, or `run_agent`-style
function); the root span goes there. Read the matching reference file for the framework instrumentor.

## Step 2 — Add dependencies

Install the OTel SDK/exporter, the common instrumentors, and one framework instrumentor. The
framework instrumentors and `opentelemetry-instrumentation-openai` are Traceloop / OpenLLMetry
packages; they're standalone (they pull in `opentelemetry-semantic-conventions-ai` themselves), so
you do **not** need `traceloop-sdk`.

```
opentelemetry-api>=1.33.0,<2.0.0          # keep the <2.0.0 cap
opentelemetry-sdk>=1.33.0
opentelemetry-exporter-otlp-proto-http>=1.33.0
opentelemetry-instrumentation-requests>=0.54b0
opentelemetry-instrumentation-httpx>=0.54b0
opentelemetry-instrumentation-aiohttp-client>=0.54b0
opentelemetry-instrumentation-openai>=0.40.5
# + one framework instrumentor (see the reference file)
```

These pins are a snapshot (templates `release/11.1.10`) and drift over time. For current versions,
**with the user's permission** fetch the real manifest (not the `custom_model/` symlink) from the
public repo:
`https://raw.githubusercontent.com/datarobot-community/datarobot-agent-templates/main/agent_<framework>/pyproject.toml`
(swap `main` for a release tag to match a specific DataRobot version). Add the result to the repo's
existing manifest.

## Step 3 — Install instrumentors, first

Create a small module (e.g. `telemetry.py`) that calls the instrumentors; importing it applies them
as a side effect:

```python
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.crewai import CrewAIInstrumentor  # framework line; per reference file

RequestsInstrumentor().instrument()
AioHttpClientInstrumentor().instrument()
HTTPXClientInstrumentor().instrument()
OpenAIInstrumentor().instrument()
CrewAIInstrumentor().instrument()
```

Run the instrumentors before the agent framework and HTTP/LLM clients are *used* — importing the
telemetry module at the top of your entry point is the simplest guarantee (instrumentors patch
libraries at `.instrument()` time, and calls made before that produce no spans, silently). If the
repo uses an import sorter (isort/Ruff), fence that import so it isn't reordered below the framework
imports.

## Step 4 — Point the exporter at DataRobot

This is a standard OTel exporter setup (`TracerProvider` + `OTLPSpanExporter` + span processor). Only
these are DataRobot-specific:

- **Endpoint**: the DataRobot host with its path replaced by `/otel` (e.g.
  `https://app.datarobot.com/otel`), or `DATAROBOT_OTEL_COLLECTOR_BASE_URL` if set.
- **Auth headers** (not a Bearer token), comma-joined in `OTEL_EXPORTER_OTLP_HEADERS`:
  `X-DataRobot-Api-Key=<token>,X-DataRobot-Entity-Id=<entity_id>`.
- **`SimpleSpanProcessor`, not `BatchSpanProcessor`** — the batch processor flushes asynchronously,
  so a short-lived agent process can exit before the flush and drop spans.
- If `OTEL_EXPORTER_OTLP_ENDPOINT`/`_HEADERS` are already set, don't override them — a DataRobot
  deployment likely sets these itself (likely-but-unconfirmed), in which case the derivation below
  only matters for local/standalone runs.

For the exact reference implementation, **with the user's permission** the agent can read the
template's `run_agent.py` from the public repo and copy its `setup_otel_env_variables` /
`setup_otel_exporter` / `setup_otel` functions:
`https://raw.githubusercontent.com/datarobot-community/datarobot-agent-templates/main/agent_<framework>/run_agent.py`.
Otherwise this minimal version encodes the four points above:

```python
import os
from urllib.parse import urlparse, urlunparse

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)


def setup_otel(entity_id: str):
    """Configure the DataRobot OTLP exporter; returns the root span. Skips cleanly if unconfigured."""
    already_set = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_HEADERS"
    )
    token = os.environ.get("DATAROBOT_API_TOKEN")
    if not already_set and entity_id and token:
        endpoint = os.environ.get("DATAROBOT_OTEL_COLLECTOR_BASE_URL", "")
        if not endpoint:
            p = urlparse(os.environ.get("DATAROBOT_ENDPOINT", ""))
            endpoint = urlunparse((p.scheme, p.netloc, "otel", "", "", ""))  # -> https://host/otel
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = (
            f"X-DataRobot-Api-Key={token},X-DataRobot-Entity-Id={entity_id}"
        )

    if "OTEL_EXPORTER_OTLP_ENDPOINT" in os.environ:
        trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
    return tracer.start_span("run_agent")
```

Log a warning when a required value is missing so it's obvious rather than silent, and never 401 on
a blank entity id — skip tracing instead.

## Step 5 — Wrap the run in the root span

`setup_otel` returns the `run_agent` span; keep it open for the whole invocation so every
framework/tool/LLM span nests under it into one trace:

```python
from opentelemetry.trace import use_span

span = setup_otel(os.environ.get("DATAROBOT_ENTITY_ID", ""))
with use_span(span, end_on_exit=True):
    result = run_the_agent(...)   # crew.kickoff(...) / graph.invoke(...) / query_engine.query(...)
```

A blank entity id is passed as `""`; `setup_otel` then skips export but still returns a span, so the
run proceeds either way.

## Step 6 — Populate the Tracing table columns

Auto-instrumentation captures most spans, but these columns come from specific attributes. Set them
on custom tools' spans (attribute names must be exact):

| Column | Attribute | Notes |
| --- | --- | --- |
| Cost | `datarobot.moderation.cost` | Numeric; summed across the trace. |
| Prompt | `gen_ai.prompt` | First value in trace order wins. |
| Completion | `gen_ai.completion` | Last value in trace order wins. |
| Tools | `tool_name` | Every distinct value on any span is listed. |

```python
with tracer.start_as_current_span("my_tool"):
    span = trace.get_current_span()
    span.set_attribute("tool_name", "my_tool")
    span.set_attribute("gen_ai.prompt", query)
    span.set_attribute("datarobot.moderation.cost", 0.0)
    result = do_work(query)
    span.set_attribute("gen_ai.completion", str(result))
```

If tool spans show in the timeline but **Tools** is empty, the framework didn't set `tool_name` —
set it on the active span yourself (common with LangGraph/LangChain callbacks; see
`references/langgraph.md`). The per-framework tool examples in the reference files come from the
DataRobot docs.

**Nested spans** (from the docs) — for a multi-step tool, nest a child span per stage:

```python
with tracer.start_as_current_span("enrich_records") as parent:
    parent.set_attribute("input.count", len(records))
    with tracer.start_as_current_span("fetch"):
        fetched = fetch(records)
    with tracer.start_as_current_span("validate"):
        valid = validate(fetched)
    parent.set_attribute("result.count", len(valid))
```

**Span events** (from the docs) — mark points in time within a span:

```python
with tracer.start_as_current_span("tool_execution") as span:
    span.add_event("processing started")
    partial = do_first_part()
    span.add_event("partial ready", {"count": len(partial)})
    result = finish(partial)
    span.add_event("processing completed", {"size": len(result)})
```

## Step 6b — Trace agent startup configuration (optional, from the docs)

Wrap config loading in a span to confirm runtime parameters loaded correctly:

```python
with tracer.start_as_current_span("config_variables"):
    span = trace.get_current_span()
    span.set_attribute("config.example_setting", config.example_setting)
    span.add_event("config attribute set on span")
```

Use `config.<name>`; never put secrets on a span. If deployed as a DataRobot custom model, a value
only appears if DataRobot injects it — declare it in `model-metadata.yaml`
(`runtimeParameterDefinitions`) and read it via `datarobot_drum.RuntimeParameters` or `os.environ`.
For local runs, set it in `.env`.

## Step 7 — Verify in development (temporary)

While building, add a `ConsoleSpanExporter` alongside the OTLP one so you can confirm spans are
actually produced — correct names, nesting, and the `tool_name` / `gen_ai.*` attributes — without
needing DataRobot credentials or a deployment:

```python
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
```

This is a development-only aid, not part of the DataRobot setup, and shouldn't ship (it clutters
stdout in production). Leave it in while iterating; **once the user confirms the implementation
works, ask their permission to remove it** — don't remove it silently, and don't leave it in
permanently.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| **401 Unauthorized** | `DATAROBOT_ENTITY_ID` missing/blank/wrong form, or token not authorized for that entity | Set a valid `<entity_type>-<entity_id>`; confirm token access. A valid token alone isn't enough. |
| **No traces at all** | Instrumentation ran *after* the framework/clients were used, or disabled by missing env vars | Import the telemetry module before the framework (Step 3); if an import sorter reorders it, fence it. Check the startup warning and supply what it names. |
| **Tools column empty** | Framework didn't set `tool_name` (LangGraph/LangChain callbacks) | Set `tool_name` on the active span (Step 6). |
| **Prompt / Completion empty** | LLM called via a non-OpenAI SDK, so `OpenAIInstrumentor` missed it | Add that provider's instrumentor, or set `gen_ai.*` manually. |
| **Cost empty** | No `datarobot.moderation.cost` set | Set the numeric attribute on the relevant span(s). |
| **Spans lost only as a script/container** | `BatchSpanProcessor` exits before flush | Use `SimpleSpanProcessor` (Step 4), or `force_flush()`/`shutdown()` before exit. |