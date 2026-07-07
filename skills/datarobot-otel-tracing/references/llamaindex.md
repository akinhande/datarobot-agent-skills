# LlamaIndex — DataRobot OTel tracing

## Framework instrumentor

```python
from opentelemetry.instrumentation.llamaindex import LlamaIndexInstrumentor
LlamaIndexInstrumentor().instrument()
```

## Dependency

```
opentelemetry-instrumentation-llamaindex>=0.40.5
```

(A Traceloop / OpenLLMetry package. It's standalone and pulls in
`opentelemetry-semantic-conventions-ai` itself; install it alongside the common instrumentors
listed in SKILL.md Step 2. `traceloop-sdk` is not needed.)

The `>=0.40.5` pin is a snapshot from templates `release/11.1.10`. Prefer deriving the current version per SKILL.md Step 2 — with the user's permission, from
`https://raw.githubusercontent.com/datarobot-community/datarobot-agent-templates/main/agent_llamaindex/pyproject.toml`.

## Full `helpers_telemetry.py` for LlamaIndex

```python
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.llamaindex import LlamaIndexInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

RequestsInstrumentor().instrument()
AioHttpClientInstrumentor().instrument()
HTTPXClientInstrumentor().instrument()
OpenAIInstrumentor().instrument()
LlamaIndexInstrumentor().instrument()
```

## Integration notes

- Import this module **before** `llama_index` is imported. Move it to the top of the entry module
  with the `# isort: off` fence (SKILL.md Step 3).
- The root span wraps the query / agent run:

  ```python
  span = tracer.start_span("run_agent")
  with use_span(span, end_on_exit=True):
      result = query_engine.query(question)   # or agent.chat(...) / agent.run(...)
  ```

- LlamaIndex tools are usually `FunctionTool` instances built from a plain function. Wrap the
  function body in a span and set the DataRobot attributes there:

  ```python
  from opentelemetry import trace
  from llama_index.core.tools import FunctionTool

  tracer = trace.get_tracer(__name__)

  def _weather_run(city: str) -> str:
      with tracer.start_as_current_span("weather_tool_fetch"):
          span = trace.get_current_span()
          span.set_attribute("tool_name", "weather_tool")
          span.set_attribute("gen_ai.prompt", f"weather lookup for {city}")
          span.set_attribute("datarobot.moderation.cost", 0.0)
          result = do_work(city)
          span.set_attribute("gen_ai.completion", result)
          return result

  def WeatherTool() -> FunctionTool:
      return FunctionTool.from_defaults(fn=_weather_run, name="weather_tool", description="...")
  ```

## End-to-end example

`telemetry.py` is identical to the CrewAI example except the framework line is
`from opentelemetry.instrumentation.llamaindex import LlamaIndexInstrumentor` /
`LlamaIndexInstrumentor().instrument()`. The entry point builds a `FunctionAgent` with the
instrumented tool and wraps the run:

```python
# main.py
# isort: off
from telemetry import setup_datarobot_otel, tracer   # FIRST — before llama_index loads
# isort: on
import asyncio, os
from opentelemetry import trace
from opentelemetry.trace import use_span
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI


def _weather_run(city: str) -> str:
    with tracer.start_as_current_span("weather_tool"):
        span = trace.get_current_span()
        span.set_attribute("tool_name", "weather_tool")
        span.set_attribute("gen_ai.prompt", city)
        span.set_attribute("datarobot.moderation.cost", 0.0)
        result = f"Sunny in {city}"
        span.set_attribute("gen_ai.completion", result)
        return result


def main() -> None:
    setup_datarobot_otel(entity_id=os.environ.get("DATAROBOT_ENTITY_ID", ""))
    tool = FunctionTool.from_defaults(fn=_weather_run, name="weather_tool",
                                      description="Look up the weather for a city.")
    agent = FunctionAgent(tools=[tool], llm=OpenAI(model="gpt-4o-mini"))
    span = tracer.start_span("run_agent")
    with use_span(span, end_on_exit=True):
        print(asyncio.run(agent.run("Weather in Paris?")))


if __name__ == "__main__":
    main()
```