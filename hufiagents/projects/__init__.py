"""Server-side project/repository registry (Phase 2B connector, ADR-010).
A task selects a project by id; the registry is the only source of a
project's clone URL, GitHub repo and test/build/lint commands -- never the
task/mission body. Mirrors risk.Policy's pattern: a pure, file-backed,
side-effect-free lookup."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    repo_url: str
    github_repo: str = ""
    default_branch: str = "main"
    allowed: bool = False
    test_command: list[str] = Field(default_factory=list)
    build_command: list[str] = Field(default_factory=list)
    lint_command: list[str] = Field(default_factory=list)


class ProjectRegistry:
    def __init__(self, path: Path):
        data = yaml.safe_load(path.read_text()) if path.exists() else {}
        self.projects = {
            project_id: Project(id=project_id, **(config or {}))
            for project_id, config in (data or {}).get("projects", {}).items()
        }

    def get(self, project_id: str) -> Project:
        project = self.projects.get(project_id)
        # Unknown and explicitly-disallowed both raise the same error: this
        # API never distinguishes "doesn't exist" from "exists but disabled"
        # for a caller, so a disabled project's existence isn't leaked.
        if project is None or not project.allowed:
            raise KeyError(project_id)
        return project
