"""hufiagents.cli (the V1 CLI surface, docs/ARCHITECTURE.md §8 approve/deny flow)
had zero test coverage before this review. It is a thin httpx client, so it is
tested here by substituting httpx.Client with an in-memory recorder instead of a
real server/socket -- consistent with how the provider adapters are tested
against httpx.MockTransport rather than a live endpoint."""

import json

import httpx
import pytest

from hufiagents import cli


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeClient:
    calls = []

    def __init__(self, *, base_url, timeout, trust_env):
        FakeClient.init_kwargs = {"base_url": base_url, "timeout": timeout, "trust_env": trust_env}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, path):
        FakeClient.calls.append(("GET", path, None, None))
        return FakeResponse({"method": "GET", "path": path})

    def post(self, path, json=None, headers=None):
        FakeClient.calls.append(("POST", path, json, headers))
        return FakeResponse({"method": "POST", "path": path, "json": json})


@pytest.fixture(autouse=True)
def fake_httpx(monkeypatch):
    FakeClient.calls = []
    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.delenv("HUFI_APPROVAL_TOKEN", raising=False)
    yield


def run(monkeypatch, argv, capsys):
    monkeypatch.setattr("sys.argv", ["hufiagents", *argv])
    cli.main()
    return capsys.readouterr().out


def test_submit_posts_outcome_and_prints_json(monkeypatch, capsys):
    out = run(monkeypatch, ["submit", "write a checklist"], capsys)
    assert FakeClient.calls == [("POST", "/missions", {"outcome": "write a checklist"}, None)]
    assert json.loads(out) == {
        "method": "POST",
        "path": "/missions",
        "json": {"outcome": "write a checklist"},
    }


def test_list_show_and_audit_use_expected_paths(monkeypatch, capsys):
    run(monkeypatch, ["list"], capsys)
    run(monkeypatch, ["show", "mission-1"], capsys)
    run(monkeypatch, ["audit", "mission-1"], capsys)
    assert FakeClient.calls == [
        ("GET", "/missions", None, None),
        ("GET", "/missions/mission-1", None, None),
        ("GET", "/audit?mission_id=mission-1", None, None),
    ]


def test_cancel_posts_with_no_body(monkeypatch, capsys):
    run(monkeypatch, ["cancel", "task-1"], capsys)
    assert FakeClient.calls == [("POST", "/tasks/task-1/cancel", None, None)]


def test_approve_sends_bearer_token_from_env_and_default_empty_note(monkeypatch, capsys):
    monkeypatch.setenv("HUFI_APPROVAL_TOKEN", "owner-secret")
    run(monkeypatch, ["approve", "approval-1"], capsys)
    assert FakeClient.calls == [
        (
            "POST",
            "/approvals/approval-1/approve",
            {"note": ""},
            {"Authorization": "Bearer owner-secret"},
        )
    ]


def test_deny_sends_note_and_empty_bearer_without_token_configured(monkeypatch, capsys):
    run(monkeypatch, ["deny", "approval-1", "--note", "outside scope"], capsys)
    assert FakeClient.calls == [
        (
            "POST",
            "/approvals/approval-1/deny",
            {"note": "outside scope"},
            {"Authorization": "Bearer "},
        )
    ]


def test_client_never_trusts_ambient_proxy_environment(monkeypatch, capsys):
    run(monkeypatch, ["list"], capsys)
    assert FakeClient.init_kwargs["trust_env"] is False
