# LangGraph / LangChain — DataRobot OTel tracing

DataRobot instruments LangGraph and LangChain projects with the **LangChain** instrumentor
(LangGraph is built on LangChain runnables, so the same instrumentor covers both).

## Framework instrumentor

```python
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
LangchainInstrumentor().instrument()
```

## Dependency

```
opentelemetry-instrumentation-langchain>=0.40.5
```

(A Traceloop / OpenLLMetry package. It's standalone and pulls in
`opentelemetry-semantic-conventions-ai` itself; install it alongside the common instrumentors
listed in SKILL.md Step 2. `traceloop-sdk` is not needed.)

The `>=0.40.5` pin is a snapshot from templates `release/11.1.10`. Prefer deriving the current version per SKILL.md Step 2 — with the user's permission, from
`https://raw.githubusercontent.com/datarobot-community/datarobot-agent-templates/main/agent_langgraph/pyproject.toml`.

## Full `helpers_telemetry.py` for LangGraph / LangChain

```python
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

RequestsInstrumentor().instrument()
AioHttpClientInstrumentor().instrument()
HTTPXClientInstrumentor().instrument()
OpenAIInstrumentor().instrument()
LangchainInstrumentor().instrument()
```

## Integration notes

- Import this module **before** `langgraph` / `langchain` are imported. Move it to the top of the
  entry module with the `# isort: off` fence (SKILL.md Step 3).
- The root span wraps the graph invocation:

  ```python
  span = tracer.start_span("run_agent")
  with use_span(span, end_on_exit=True):
      result = graph.invoke(state)      # or app.invoke(...) / graph.stream(...)
  ```

- **Tools column caveat (important for LangGraph):** LangGraph often wires tool calls through
  callbacks in a way that does not attach `tool_name` to the span. If tool execution shows in the
  span timeline but the **Tools** column stays empty, set the name manually inside the tool:

  ```python
  from opentelemetry import trace

  def my_tool_impl(query: str) -> str:
      with trace.get_tracer(__name__).start_as_current_span("my_tool"):
          span = trace.get_current_span()
          span.set_attribute("tool_name", "my_tool")
          span.set_attribute("gen_ai.prompt", query)
          span.set_attribute("datarobot.moderation.cost", 0.0)
          result = do_work(query)
          span.set_attribute("gen_ai.completion", result)
          return result
  ```

  Or, if a span is already active from upstream instrumentation, just set `tool_name` on
  `trace.get_current_span()`.

## Tool example (from the DataRobot docs)

This is the LangGraph custom-tool tracing example from DataRobot's docs
(`agentic-tracing-code.html`, LangGraph tab). It assumes the exporter and the `run_agent` root span
are already wired per SKILL.md Steps 3–5. The docs use a `langchain.tools.BaseTool` subclass (the
`@tool` decorator form works too — use whichever your codebase already uses). Because LangGraph
routes tool calls through callbacks, setting `tool_name` on the span here is what makes the tool
appear in the **Tools** column.

```python
import requests
from langchain.tools import BaseTool
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class WeatherTool(BaseTool):
    name: str = "weather_tool"
    description: str = (
        "Fetches the current weather for a specified city. "
        "Requires an API key from OpenWeatherMap."
    )

    def _run(self, city: str) -> str:
        with tracer.start_as_current_span("weather_tool_fetch"):
            current_span = trace.get_current_span()
            current_span.set_attribute("tool_name", "weather_tool")
            current_span.set_attribute("gen_ai.prompt", f"weather lookup for {city}")
            current_span.set_attribute("datarobot.moderation.cost", 0.0)

            # Custom attribute (extra span detail; not a Tracing-table column)
            current_span.set_attribute("weather.city", city)

            api_key = "YOUR_API_KEY"  # Replace with your API key
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            params = {"q": city, "appid": api_key, "units": "metric"}

            try:
                response = requests.get(base_url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                current_span.set_attribute("weather.temperature", data["main"]["temp"])

                result = f"Temperature in {city}: {data['main']['temp']}°C"
                current_span.set_attribute("gen_ai.completion", result)
                return result

            except requests.exceptions.RequestException as e:
                current_span.set_attribute("weather.error", str(e))
                err = f"Error: {str(e)}"
                current_span.set_attribute("gen_ai.completion", err)
                return err
```
## Create nested spans (from the DataRobot docs)

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def complex_tool_workflow(input_data):
    with tracer.start_as_current_span("complex_tool_main"):
        current_span = trace.get_current_span()
        current_span.set_attribute("input.size", len(input_data))

        # First step in the workflow
        with tracer.start_as_current_span("data_processing"):
            processed_data = process_data(input_data)
            trace.get_current_span().set_attribute("processed_items", len(processed_data))

        # Second step in the workflow
        with tracer.start_as_current_span("data_validation"):
            validated_data = validate_data(processed_data)
            trace.get_current_span().set_attribute("validated_items", len(validated_data))

        # Third step in the workflow
        with tracer.start_as_current_span("result_generation"):
            result = generate_result(validated_data)
            current_span.set_attribute("result.size", len(result))

        return result
```
