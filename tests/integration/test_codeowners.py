# Copyright (c) 2026 DataRobot, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Validate CODEOWNERS rules for the skills/ directory:
- No skill directory should be owned by @datarobot-oss/datarobot-agent-skills
  (that team owns repo scaffolding only, not individual skills)
"""

from pathlib import Path

import pytest
from codeowners import CodeOwners

REPO_ROOT = Path(__file__).parent.parent.parent
CODEOWNERS_FILE = REPO_ROOT / ".github" / "CODEOWNERS"
SKILLS_DIR = REPO_ROOT / "skills"
DEFAULT_OWNER = "@datarobot-oss/datarobot-agent-skills"


def skill_dirs() -> list[Path]:
    return [
        item
        for item in SKILLS_DIR.iterdir()
        if item.is_dir() and (item / "SKILL.md").exists()
    ]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "skill_dir" in metafunc.fixturenames:
        dirs = skill_dirs()
        metafunc.parametrize("skill_dir", dirs, ids=[d.name for d in dirs])


def test_codeowners_file_exists() -> None:
    assert CODEOWNERS_FILE.exists(), ".github/CODEOWNERS not found"


def test_skill_not_owned_by_default_team(skill_dir: Path) -> None:
    """Each skill must have an explicit owner that is not the default repo team."""
    text = CODEOWNERS_FILE.read_text(encoding="utf-8")
    co = CodeOwners(text)
    # Use a representative file inside the skill dir for ownership lookup
    rel_path = str((skill_dir / "SKILL.md").relative_to(REPO_ROOT))
    owners = [owner for (_kind, owner) in co.of(rel_path)]
    assert owners, (
        f"Skill '{skill_dir.name}' has no CODEOWNERS entry — add an explicit rule"
    )
    assert DEFAULT_OWNER not in owners, (
        f"Skill '{skill_dir.name}' is owned by {DEFAULT_OWNER}, "
        "which should only own repo scaffolding. "
        "Add a specific team or user to CODEOWNERS for this skill."
    )
