"""ProjectRegistry (docs/DECISIONS.md ADR-010): the only source of a
project's repo_url/github_repo/commands. Mirrors risk.Policy's own test
style -- a pure, file-backed, side-effect-free lookup."""

import pytest
import yaml

from hufiagents.projects import ProjectRegistry


def write_registry(tmp_path, projects):
    path = tmp_path / "projects.yaml"
    path.write_text(yaml.dump({"projects": projects}))
    return path


def test_returns_a_configured_allowed_project(tmp_path):
    path = write_registry(
        tmp_path,
        {
            "demo": {
                "repo_url": "https://example.test/demo.git",
                "github_repo": "org/demo",
                "default_branch": "main",
                "allowed": True,
                "test_command": ["npm", "test"],
            }
        },
    )
    registry = ProjectRegistry(path)
    project = registry.get("demo")
    assert project.id == "demo"
    assert project.repo_url == "https://example.test/demo.git"
    assert project.test_command == ["npm", "test"]


def test_unknown_project_raises_keyerror(tmp_path):
    registry = ProjectRegistry(write_registry(tmp_path, {}))
    with pytest.raises(KeyError):
        registry.get("does-not-exist")


def test_disallowed_project_raises_keyerror_not_a_different_error(tmp_path):
    """Disabled and unknown must be indistinguishable to a caller -- a
    disabled project's existence/config is never leaked (docs/DECISIONS.md
    ADR-010)."""
    path = write_registry(
        tmp_path, {"disabled": {"repo_url": "https://example.test/x.git", "allowed": False}}
    )
    registry = ProjectRegistry(path)
    with pytest.raises(KeyError):
        registry.get("disabled")


def test_missing_registry_file_yields_empty_registry(tmp_path):
    registry = ProjectRegistry(tmp_path / "does-not-exist.yaml")
    assert registry.projects == {}
    with pytest.raises(KeyError):
        registry.get("anything")
