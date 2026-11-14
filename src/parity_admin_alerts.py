"""Alert on missed or failed Even/Odd production jobs."""
import json
import os
from datetime import datetime, time, timezone
from pathlib import Path

from parity_discord import RESERVATION, discord_send, github, reservation
from parity_research import CENTRAL

WORKFLOWS = {
    "parity-model-evidence-sync.yml": ("Picks", time(7, 15)),
    "parity-recaps.yml": ("Individual results and recaps", time(9, 15)),
}
FAILED = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}


def missed(runs, now, deadline):
    if now.time() < deadline:
        return False
    return not any(datetime.fromisoformat(run["created_at"]).astimezone(CENTRAL).date()
                   == now.date() for run in runs)


def notify(repo, label, detail, key, link):
    issue = reservation(repo, "StatRally Even/Odd admin | " + key)
    if issue is None:
        return
    message_id = discord_send(os.environ["STATRALLY_ADMIN_DISCORD_WEBHOOK"], {
        "content": f"🚨 **StatRally Admin | {label}**\n{detail}\n{link}",
        "allowed_mentions": {"parse": []},
    })
    response = github("PATCH", repo, f"/issues/{issue}", {
        "state": "closed",
        "body": RESERVATION + json.dumps({"status": "confirmed", "message_id": message_id}),
    })
    if response.get("number") != issue:
        raise RuntimeError("Admin alert receipt not confirmed")


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    if not os.environ.get("STATRALLY_ADMIN_DISCORD_WEBHOOK"):
        raise RuntimeError("Admin Discord webhook missing")
    now = datetime.now(timezone.utc).astimezone(CENTRAL)
    event = os.environ["GITHUB_EVENT_NAME"]
    if event == "workflow_run":
        run = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["workflow_run"]
        workflow = run["path"].split("/")[-1]
        if workflow in WORKFLOWS and run["head_branch"] == "main" and run["conclusion"] in FAILED:
            label, _ = WORKFLOWS[workflow]
            notify(repo, label, f"Workflow ended with status {run['conclusion']}. Check the failed steps.",
                   str(run["id"]), f"https://github.com/{repo}/actions/runs/{run['id']}")
        return
    if event == "push":
        print("Admin alert monitor deployed and webhook configured")
        return
    for workflow, (label, deadline) in WORKFLOWS.items():
        response = github("GET", repo, f"/actions/workflows/{workflow}/runs?event=schedule&branch=main&per_page=20")
        if missed(response["workflow_runs"], now, deadline):
            notify(repo, label, f"No scheduled run recorded for {now.date()} Central.",
                   f"{workflow} | {now.date()}", f"https://github.com/{repo}/actions/workflows/{workflow}")


if __name__ == "__main__":
    main()
