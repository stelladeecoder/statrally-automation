"""Alert on missed or failed Even/Odd production jobs."""
import json
import os
from datetime import datetime, time, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from parity_discord import RESERVATION, discord_send, github, reservation
from parity_research import CENTRAL

WORKFLOWS = {
    "parity-model-evidence-sync.yml": ("Picks", time(7, 15)),
    "parity-recaps.yml": ("Individual results and recaps", time(21, 15)),
}
FAILED = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}


def missed(runs, now, deadline):
    if now.time() < deadline:
        return False
    return not any(datetime.fromisoformat(run["created_at"]).astimezone(CENTRAL).date()
                   == now.date() for run in runs)



def dispatch_recovery(repo, workflow):
    """Dispatch a manual recovery run when GitHub misses a scheduled trigger."""
    req = Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches",
        data=json.dumps({"ref": "main"}).encode(),
        method="POST",
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urlopen(req, timeout=25) as response:
        if response.status != 204:
            raise RuntimeError(f"Recovery rejected: HTTP {response.status}")


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
        print("Checking for missed runs after monitor deployment")
    for workflow, (label, deadline) in WORKFLOWS.items():
        response = github("GET", repo, f"/actions/workflows/{workflow}/runs?branch=main&per_page=100")
        runs = [run for run in response["workflow_runs"]
                if run.get("event") in ("schedule", "workflow_dispatch")]
        if missed(runs, now, deadline):
            try:
                dispatch_recovery(repo, workflow)
                print(f"Recovery dispatched: {label} ({now.date()} Central)")
            except Exception as exc:
                notify(repo, label,
                       f"Scheduled run missing for {now.date()} Central; recovery failed "
                       f"({type(exc).__name__}). Manual action required.",
                       f"{workflow} | {now.date()}",
                       f"https://github.com/{repo}/actions/workflows/{workflow}")
                raise


if __name__ == "__main__":
    main()
