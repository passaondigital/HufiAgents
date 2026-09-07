import argparse
import json
import os

import httpx


def main():
    parser = argparse.ArgumentParser(description="HufiAgents HTTP client")
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    commands.add_parser("list")
    submit = commands.add_parser("submit")
    submit.add_argument("outcome")
    for name in ["show", "audit", "approve", "deny", "cancel"]:
        command = commands.add_parser(name)
        command.add_argument("id")
        if name in ["approve", "deny"]:
            command.add_argument("--note", default="")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        from hufiagents.config import Settings

        # Loopback-only, always -- a reverse proxy is the only public
        # listener (docs/V1-OPERATIONS.md). Port comes from Settings
        # (HUFI_PORT) so multiple environments never need code changes.
        uvicorn.run(
            "hufiagents.api:create_app",
            factory=True,
            host="127.0.0.1",
            port=Settings().port,
            workers=1,
        )
        return
    with httpx.Client(base_url=args.url, timeout=15, trust_env=False) as client:
        if args.command == "submit":
            response = client.post("/missions", json={"outcome": args.outcome})
        elif args.command in ["approve", "deny"]:
            response = client.post(
                f"/approvals/{args.id}/{args.command}",
                json={"note": args.note},
                headers={"Authorization": "Bearer " + os.environ.get("HUFI_APPROVAL_TOKEN", "")},
            )
        elif args.command == "cancel":
            response = client.post(f"/tasks/{args.id}/cancel")
        else:
            path = (
                "/missions"
                if args.command == "list"
                else (
                    f"/missions/{args.id}"
                    if args.command == "show"
                    else f"/audit?mission_id={args.id}"
                )
            )
            response = client.get(path)
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
