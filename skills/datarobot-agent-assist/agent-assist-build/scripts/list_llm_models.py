#!/usr/bin/env python3
# Copyright (c) 2026 DataRobot, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""List available LLM models from DataRobot (gateway catalog and deployed LLMs).

This script lists active models from the LLM Gateway catalog and DataRobot-deployed
TextGeneration deployments. Designed for AI agents to discover available LLM models.

Usage:
    python list_llm_models.py [--json|--table] [--target-dir <directory>]

Environment Variables:
    DATAROBOT_ENDPOINT: DataRobot API endpoint URL
    DATAROBOT_API_TOKEN: DataRobot API authentication token
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from env_utils import get_datarobot_credentials

SOURCE_GATEWAY = "gateway"
SOURCE_DEPLOYED = "deployed"
DEPLOYED_LLM_MODEL = "datarobot-deployed-llm"
TARGET_TYPE_TEXT_GENERATION = "TextGeneration"


class LLMModel(TypedDict):
    id: str
    name: str
    source: str
    provider: str
    api_model: str
    deployment_id: str
    description: str
    context_size: int


def normalize_gateway_model(model: str) -> str:
    """Strip datarobot/ prefix from gateway model paths."""
    while model.startswith("datarobot/"):
        model = model[len("datarobot/") :]
    return model


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _map_gateway_catalog_entry(entry: dict[str, object]) -> LLMModel | None:
    if not entry.get("isActive", False):
        return None
    model_field = str(entry.get("model") or "")
    if not model_field:
        return None
    llm_id = str(entry.get("llmId") or model_field)
    api_model = normalize_gateway_model(model_field)
    name = str(entry.get("name") or api_model)
    mapped: LLMModel = {
        "id": llm_id,
        "name": name,
        "source": SOURCE_GATEWAY,
        "provider": str(entry.get("provider") or "Unknown"),
        "api_model": api_model,
        "deployment_id": "",
        "description": str(entry.get("description") or ""),
        "context_size": _as_int(entry.get("contextSize")),
    }
    return mapped


def _map_deployed_entry(entry: dict[str, object]) -> LLMModel | None:
    model_info = entry.get("model")
    if not isinstance(model_info, dict):
        return None
    if model_info.get("targetType") != TARGET_TYPE_TEXT_GENERATION:
        return None
    if str(entry.get("status") or "").lower() != "active":
        return None
    deployment_id = str(entry.get("id") or "")
    if not deployment_id:
        return None
    label = str(entry.get("label") or deployment_id)
    mapped: LLMModel = {
        "id": deployment_id,
        "name": label,
        "source": SOURCE_DEPLOYED,
        "provider": "",
        "api_model": DEPLOYED_LLM_MODEL,
        "deployment_id": deployment_id,
        "description": str(entry.get("description") or ""),
        "context_size": 0,
    }
    return mapped


def _map_cli_entry(entry: dict[str, object]) -> LLMModel:
    source = str(entry.get("source") or SOURCE_GATEWAY)
    deployment_id = str(entry.get("deployment_id") or "")
    model_id = str(entry.get("id") or "")
    name = str(entry.get("name") or model_id)
    if source == SOURCE_DEPLOYED:
        api_model = DEPLOYED_LLM_MODEL
        provider = ""
    else:
        api_model = normalize_gateway_model(str(entry.get("model") or model_id))
        provider = str(entry.get("provider") or "Unknown")
    mapped: LLMModel = {
        "id": model_id,
        "name": name,
        "source": source,
        "provider": provider,
        "api_model": api_model,
        "deployment_id": deployment_id,
        "description": str(entry.get("description") or ""),
        "context_size": _as_int(entry.get("context_size")),
    }
    return mapped


def _fetch_json_paginated(
    start_url: str, api_token: str, label: str
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    url: str | None = start_url
    while url:
        request = Request(
            url,
            headers={"Authorization": f"Bearer {api_token}"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as e:
            raise RuntimeError(f"Failed to fetch {label}: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse {label} response: {e}") from e

        if isinstance(data, dict) and "data" in data:
            page = data["data"]
            next_url = data.get("next")
        elif isinstance(data, list):
            page = data
            next_url = None
        else:
            raise RuntimeError(f"Unexpected {label} response format: {type(data)}")

        if not isinstance(page, list):
            raise RuntimeError(f"Unexpected {label} page format: {type(page)}")

        results.extend(page)
        url = str(next_url) if next_url else None
    return results


def _fetch_gateway_models_rest(endpoint: str, api_token: str) -> list[LLMModel]:
    url = f"{endpoint.rstrip('/')}/genai/llmgw/catalog/?limit=100"
    raw = _fetch_json_paginated(url, api_token, "LLM Gateway catalog")
    models: list[LLMModel] = []
    for entry in raw:
        mapped = _map_gateway_catalog_entry(entry)
        if mapped:
            models.append(mapped)
    return models


def _fetch_deployed_models_rest(endpoint: str, api_token: str) -> list[LLMModel]:
    base = endpoint.rstrip("/")
    url = (
        f"{base}/deployments/?championModelTargetType={TARGET_TYPE_TEXT_GENERATION}"
        "&limit=100"
    )
    raw = _fetch_json_paginated(url, api_token, "deployed LLMs")
    models: list[LLMModel] = []
    for entry in raw:
        mapped = _map_deployed_entry(entry)
        if mapped:
            models.append(mapped)
    return models


def _fetch_llm_models_via_cli(
    endpoint: str, api_token: str
) -> tuple[list[LLMModel], list[str]]:
    env = os.environ.copy()
    env["DATAROBOT_ENDPOINT"] = endpoint
    env["DATAROBOT_API_TOKEN"] = api_token
    try:
        result = subprocess.run(
            ["dr", "llm-gateway", "list", "--output-format", "json"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
    except FileNotFoundError as e:
        raise RuntimeError("dr CLI not found") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("dr llm-gateway list timed out") from e

    warnings: list[str] = []
    if result.stderr.strip():
        warnings.extend(
            line.strip() for line in result.stderr.splitlines() if line.strip()
        )

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"dr llm-gateway list failed: {detail}")

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError("Failed to parse dr llm-gateway list JSON output") from e

    llms = envelope.get("llms")
    if not isinstance(llms, list):
        raise RuntimeError("Unexpected dr llm-gateway list JSON format")

    return [
        _map_cli_entry(entry) for entry in llms if isinstance(entry, dict)
    ], warnings


def fetch_llm_models(endpoint: str, api_token: str) -> list[LLMModel]:
    """Fetch active LLMs from gateway catalog and deployed TextGeneration models.

    Uses ``dr llm-gateway list`` when available; falls back to direct REST calls.
    Each source is best-effort: warnings are logged to stderr when one source fails.
    """
    warnings: list[str] = []

    try:
        models, cli_warnings = _fetch_llm_models_via_cli(endpoint, api_token)
        warnings.extend(cli_warnings)
        if models:
            for warning in warnings:
                print(f"Warning: {warning}", file=sys.stderr)
            return models
        warnings.append("dr llm-gateway list returned no models")
    except RuntimeError as e:
        warnings.append(str(e))

    gateway_models: list[LLMModel] = []
    deployed_models: list[LLMModel] = []

    try:
        gateway_models = _fetch_gateway_models_rest(endpoint, api_token)
    except RuntimeError as e:
        warnings.append(str(e))

    try:
        deployed_models = _fetch_deployed_models_rest(endpoint, api_token)
    except RuntimeError as e:
        warnings.append(str(e))

    models = gateway_models + deployed_models
    if not models:
        joined = "; ".join(warnings) if warnings else "no models available"
        raise RuntimeError(f"Failed to list LLM models: {joined}")

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    return models


def format_as_table(models: list[LLMModel]) -> str:
    """Format models as a readable table."""
    if not models:
        return "No models available"

    id_width = max(len(m["id"]) for m in models)
    id_width = max(id_width, len("ID"))
    name_width = max(len(m["name"]) for m in models)
    name_width = max(name_width, len("Name"))
    source_width = max(len(m["source"]) for m in models)
    source_width = max(source_width, len("Source"))
    provider_width = max(len(m["provider"] or "-") for m in models)
    provider_width = max(provider_width, len("Provider"))
    context_width = max(len(str(m["context_size"] or "-")) for m in models)
    context_width = max(context_width, len("Context"))

    header = (
        f"{'ID':<{id_width}} | {'Name':<{name_width}} | {'Source':<{source_width}} | "
        f"{'Provider':<{provider_width}} | {'Context':>{context_width}}"
    )
    lines = [header, "-" * len(header)]
    for m in models:
        provider = m["provider"] or "-"
        context = str(m["context_size"]) if m["context_size"] > 0 else "-"
        lines.append(
            f"{m['id']:<{id_width}} | {m['name']:<{name_width}} | "
            f"{m['source']:<{source_width}} | {provider:<{provider_width}} | "
            f"{context:>{context_width}}"
        )
    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="List available LLM models (gateway catalog and deployed LLMs)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format (default: table)",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="Output in table format (default)",
    )
    parser.add_argument(
        "--target-dir",
        required=True,
        help="Project directory for .env lookup (required — use the session <target_dir>)",
    )
    args = parser.parse_args()

    target_dir = Path(args.target_dir).resolve()
    if not target_dir.is_dir():
        print(f"Error: target directory does not exist: {target_dir}", file=sys.stderr)
        return 1
    endpoint, api_token = get_datarobot_credentials(target_dir)

    if not endpoint and not api_token:
        print("Error: DATAROBOT_ENDPOINT environment variable not set", file=sys.stderr)
        print(
            "Error: DATAROBOT_API_TOKEN environment variable not set", file=sys.stderr
        )
        return 1

    if not endpoint:
        print("Error: DATAROBOT_ENDPOINT environment variable not set", file=sys.stderr)
        return 1

    if not api_token:
        print(
            "Error: DATAROBOT_API_TOKEN environment variable not set", file=sys.stderr
        )
        return 1

    try:
        models = fetch_llm_models(endpoint, api_token)

        if args.json:
            print(json.dumps(models, indent=2))
        else:
            print(f"\nFound {len(models)} active LLM models:\n")
            print(format_as_table(models))
            print()

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
