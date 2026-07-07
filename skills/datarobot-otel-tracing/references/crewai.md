# CrewAI — DataRobot OTel tracing

## Framework instrumentor

```python
from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
CrewAIInstrumentor().instrument()
```

## Dependency

```
opentelemetry-instrumentation-crewai>=0.40.5
```
The `>=0.40.5` pin is a snapshot from templates `release/11.1.10`. Prefer deriving the current version per SKILL.md Step 2 — with the user's permission, from
`https://raw.githubusercontent.com/datarobot-community/datarobot-agent-templates/main/agent_crewai/pyproject.toml`.

## Full `helpers_telemetry.py` for CrewAI

```python
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

RequestsInstrumentor().instrument()
AioHttpClientInstrumentor().instrument()
HTTPXClientInstrumentor().instrument()
OpenAIInstrumentor().instrument()
CrewAIInstrumentor().instrument()
```

## Integration notes

- Import this module **before** `crewai` is imported anywhere. If the entry module already does
  `from crewai import Crew` above the telemetry import, move the telemetry import to the very top
  (use the `# isort: off` fence shown in SKILL.md Step 3).
- The root span wraps the `kickoff`:

  ```python
  span = tracer.start_span("run_agent")
  with use_span(span, end_on_exit=True):
      result = crew.kickoff(inputs=inputs)
  ```

- CrewAI's instrumentor generally sets tool spans and names for you, so the **Tools** column
  usually populates without manual `tool_name` attributes. Add custom attributes only for tools you
  want richer detail on (see SKILL.md Step 6).
- Custom tools that subclass `crewai.tools.BaseTool`: wrap the body of `_run` in
  `tracer.start_as_current_span(...)` and set `gen_ai.prompt` / `gen_ai.completion` /
  `datarobot.moderation.cost` there.
- Following the DataRobot docs' tool example, you can also attach domain-specific attributes on the
  same span (e.g. `span.set_attribute("weather.city", city)`, `span.set_attribute("result.status",
  "success")`). Only `tool_name` / `gen_ai.prompt` / `gen_ai.completion` / `datarobot.moderation.cost`
  map to Tracing-table columns; the rest are extra detail in the span view. Among the three
  frameworks, only the tool base class/import differs — here `crewai.tools.BaseTool`.

## Tool example (from the DataRobot docs)

This is the CrewAI custom-tool tracing example from DataRobot's docs
(`agentic-tracing-code.html`, CrewAI tab). It assumes the exporter and the `run_agent` root span are
already wired per SKILL.md Steps 3–5; the tool itself just opens a span and sets attributes. Note
the framework-specific base class `crewai.tools.BaseTool`.

```python
import requests
from crewai.tools import BaseTool
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

            # Custom attributes (extra span detail; not Tracing-table columns)
            current_span.set_attribute("weather.city", city)
            current_span.set_attribute("weather.api", "openweathermap")

            api_key = "YOUR_API_KEY"  # Replace with your API key
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            params = {"q": city, "appid": api_key, "units": "metric"}

            try:
                response = requests.get(base_url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                weather = data["weather"][0]
                main = data["main"]

                current_span.set_attribute("weather.temperature", main["temp"])
                current_span.set_attribute("weather.condition", weather["main"])

                result = (
                    f"Current weather in {data['name']}, {data['sys']['country']}:\n"
                    f"Temperature: {main['temp']}°C (feels like {main['feels_like']}°C)\n"
                    f"Condition: {weather['main']} - {weather['description']}\n"
                    f"Humidity: {main['humidity']}%\n"
                    f"Pressure: {main['pressure']} hPa"
                )
                current_span.set_attribute("gen_ai.completion", result)
                return result

            except requests.exceptions.RequestException as e:
                current_span.set_attribute("weather.error", str(e))
                err = f"Error fetching weather data: {str(e)}"
                current_span.set_attribute("gen_ai.completion", err)
                return err
```