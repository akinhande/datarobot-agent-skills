# Copyright (c) 2026 DataRobot, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Spec-conformance test for the org-set scaling limit fields the
`datarobot-workload-api` skill documents.

The skill teaches agents to read `maxConcurrentWorkloads` and
`maxWorkloadReplicas` from the user / org / org-user schemas, and to recognize
the 403 the API returns when those caps are exceeded.  If DataRobot ever
renames or removes those fields in the public OpenAPI spec, the skill becomes
silently misleading.  This test catches that drift.

It fetches the published spec from docs.datarobot.com.  When the network is
unavailable, the test skips cleanly rather than failing.
"""

from __future__ import annotations

from typing import Any

import pytest

PUBLIC_SPEC_URL = (
    "https://docs.datarobot.com/en/docs/api/reference/public-api/openapi.yaml"
)

# The (schema, property) pairs the skill claims the spec exposes.  If any of
# these go missing or get renamed, both this test AND the skill need an update.
REQUIRED_LIMIT_FIELDS: list[tuple[str, str]] = [
    ("OrganizationRetrieve", "maxConcurrentWorkloads"),
    ("OrganizationRetrieve", "maxWorkloadReplicas"),
    ("OrganizationUserResponse", "maxConcurrentWorkloads"),
    ("OrganizationUserResponse", "maxWorkloadReplicas"),
    ("UserRetrieveResponse", "maxConcurrentWorkloads"),
    ("UserRetrieveResponse", "maxWorkloadReplicas"),
]


@pytest.fixture(scope="module")
def public_spec() -> dict[str, Any]:
    """Fetch + parse the public OpenAPI spec.  Skip the test if offline."""
    try:
        import httpx
        import yaml
    except ImportError as e:
        pytest.skip(f"required dependency unavailable: {e}")
    try:
        r = httpx.get(PUBLIC_SPEC_URL, timeout=20.0, follow_redirects=True)
    except httpx.HTTPError as e:
        pytest.skip(f"could not fetch public spec ({type(e).__name__}: {e})")
    if r.status_code != 200:
        pytest.skip(f"public spec fetch returned {r.status_code}")
    return dict(yaml.safe_load(r.text))


@pytest.mark.parametrize(("schema_name", "prop"), REQUIRED_LIMIT_FIELDS)
def test_limit_field_present_in_public_spec(
    public_spec: dict[str, Any], schema_name: str, prop: str
) -> None:
    """The skill claims this (schema, property) pair exists. Verify against the live spec."""
    schemas = public_spec.get("components", {}).get("schemas", {})
    assert schema_name in schemas, (
        f"Schema {schema_name!r} not found in the public OpenAPI spec. "
        f"The datarobot-workload-api skill references it in references/schema-reference.md "
        f"and SKILL.md — update both if the schema was renamed."
    )
    props = schemas[schema_name].get("properties") or {}
    assert prop in props, (
        f"Property {schema_name}.{prop} not found in the public OpenAPI spec. "
        f"The datarobot-workload-api skill teaches agents to read this field — update the skill "
        f"if it was renamed or removed."
    )


def test_limit_fields_documented_in_skill() -> None:
    """The skill text should mention both limit field names so an agent searching for them finds the guidance."""
    from pathlib import Path

    skill_md = (
        Path(__file__).resolve().parents[2] / "skills/datarobot-workload-api/SKILL.md"
    ).read_text()
    for field in ("maxConcurrentWorkloads", "maxWorkloadReplicas"):
        assert field in skill_md, (
            f"SKILL.md should mention {field!r} so an agent grepping for it finds the "
            f"org-set scaling limits guidance. If you removed it intentionally, also update "
            f"this test."
        )
