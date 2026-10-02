#!/usr/bin/env python3
"""Outer loop for the overnight run: one fresh `claude -p` per task, with usage-limit handling.

Run it inside the sandbox VM, not on your main machine (it passes --dangerously-skip-permissions).

    python3 scripts/overnight.py --min-remaining-pct 10 --wait-for-reset

Each iteration's `claude` output includes a `rate_limit_event` with how much of the five-hour and
weekly usage windows is used and when each resets. After every finished task the loop checks it:

  --min-remaining-pct N   stop (or wait, see below) when either window has less than N% left,
                          so a task is never started that the window can't finish
  --wait-for-reset        instead of stopping, sleep until the window resets and carry on
                          (only if the reset is within --max-wait-hours, so a nearly used-up
                          weekly window still stops the run)

If the limit is hit in the middle of a task anyway, that iteration doesn't count as a stall:
with --wait-for-reset the loop sleeps until the reset and retries, otherwise it stops. The
prompt tells the next iteration to finish any interrupted task first.

Exit codes: 0 = PROGRESS.md says DONE, 1 = stuck (no commits), 2 = iteration cap reached,
3 = stopped because of usage.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OK_STATUSES = {"allowed", "allowed_warning"}
LIMIT_TEXT = re.compile(r"usage limit|rate limit|limit reached|limit will reset", re.IGNORECASE)
RESET_EPOCH_IN_TEXT = re.compile(r"\|(\d{10})\b")
MAX_LIMIT_STREAK = 3


@dataclass
class Window:
    utilization: float | None = None  # share of the window used, 0.0-1.0
    resets_at: int | None = None  # epoch seconds

    @property
    def remaining_pct(self) -> float | None:
        if self.utilization is None:
            return None
        return (1 - self.utilization) * 100


@dataclass
class RunSummary:
    model: str | None = None
    status: str | None = None
    limit_reset: int | None = None
    five_hour: Window = field(default_factory=Window)
    seven_day: Window = field(default_factory=Window)
    is_error: bool = False
    result_text: str = ""
    cost_usd: float = 0.0
    returncode: int = 0

    @property
    def limit_hit(self) -> bool:
        blocked = self.status is not None and self.status not in OK_STATUSES
        return blocked or (self.is_error and bool(LIMIT_TEXT.search(self.result_text)))

    @property
    def reset_at(self) -> int | None:
        if self.limit_reset:
            return self.limit_reset
        match = RESET_EPOCH_IN_TEXT.search(self.result_text)
        if match:
            return int(match.group(1))
        return self.five_hour.resets_at


@dataclass
class Action:
    kind: str  # "continue", "wait" or "stop"
    reason: str = ""
    until: float = 0.0  # epoch to sleep until, for "wait"


def update_summary(summary: RunSummary, event: dict) -> None:
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        summary.model = event.get("model")
    elif kind == "rate_limit_event":
        info = event.get("rate_limit_info", {})
        summary.status = info.get("status", summary.status)
        summary.limit_reset = info.get("resetsAt", summary.limit_reset)
        windows = info.get("unifiedWindows", {})
        for name, window in (("five_hour", summary.five_hour), ("seven_day", summary.seven_day)):
            data = windows.get(name)
            if data:
                window.utilization = data.get("utilization")
                window.resets_at = data.get("resetsAt")
    elif kind == "result":
        summary.is_error = bool(event.get("is_error"))
        summary.result_text = str(event.get("result") or "")
        summary.cost_usd = event.get("total_cost_usd") or 0.0


def wait_or_stop(reason: str, reset_times: list, cfg, now: float) -> Action:
    can_wait = (
        cfg.wait_for_reset
        and all(reset_times)
        and max(reset_times) - now <= cfg.max_wait_hours * 3600
    )
    if can_wait:
        return Action("wait", reason, max(reset_times) + cfg.reset_margin_sec)
    return Action("stop", reason)


def decide(summary: RunSummary, cfg, now: float) -> Action:
    if summary.limit_hit:
        return wait_or_stop("usage limit hit mid-task", [summary.reset_at], cfg, now)
    if cfg.min_remaining_pct is None:
        return Action("continue")

    low = []
    for name, window in (("five-hour", summary.five_hour), ("weekly", summary.seven_day)):
        remaining = window.remaining_pct
        if remaining is not None and remaining < cfg.min_remaining_pct:
            low.append((f"{name} window has {remaining:.0f}% left", window.resets_at))
    if not low:
        return Action("continue")
    reasons = "; ".join(reason for reason, _ in low)
    return wait_or_stop(reasons, [reset for _, reset in low], cfg, now)


def describe_tool_use(event: dict) -> str | None:
    if event.get("type") != "assistant":
        return None
    for block in event.get("message", {}).get("content", []):
        if block.get("type") == "tool_use":
            args = block.get("input", {})
            detail = args.get("command") or args.get("file_path") or args.get("description") or ""
            return f"  {block.get('name')}: {str(detail).splitlines()[0][:90] if detail else ''}"
    return None


def run_iteration(cfg, prompt: str, log_path: Path) -> RunSummary:
    command = [
        cfg.claude_bin, "-p", prompt,
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--verbose",
    ]
    if cfg.model:
        command += ["--model", cfg.model]
    if cfg.effort:
        command += ["--effort", cfg.effort]

    summary = RunSummary()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as log, subprocess.Popen(
        command,
        cwd=cfg.repo,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as process:
        for line in process.stdout:
            log.write(line)
            try:
                event = json.loads(line)
            except ValueError:
                continue
            update_summary(summary, event)
            tool_line = describe_tool_use(event)
            if tool_line:
                print(tool_line, flush=True)
    summary.returncode = process.returncode
    return summary


def git_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def is_done(repo: Path) -> bool:
    return "DONE" in (repo / "PROGRESS.md").read_text().splitlines()


def sleep_until(epoch: float) -> None:
    while (left := epoch - time.time()) > 0:
        time.sleep(min(60, left))


def usage_text(summary: RunSummary) -> str:
    parts = []
    for name, window in (("5h", summary.five_hour), ("7d", summary.seven_day)):
        if window.remaining_pct is not None:
            parts.append(f"{name} {window.remaining_pct:.0f}% left")
    return ", ".join(parts) or "usage unknown"


def parse_args(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--prompt-file", type=Path, default=REPO / "scripts" / "overnight_prompt.txt")
    parser.add_argument("--claude-bin", default=os.environ.get("CLAUDE_BIN", "claude"))
    parser.add_argument("--model", default=None)
    parser.add_argument("--effort", default=None)
    parser.add_argument("--max-iterations", type=int, default=int(os.environ.get("MAX_ITERATIONS", 40)))
    parser.add_argument("--stall-limit", type=int, default=int(os.environ.get("STALL_LIMIT", 3)))
    parser.add_argument("--min-remaining-pct", type=float, default=None)
    parser.add_argument("--wait-for-reset", action="store_true")
    parser.add_argument("--max-wait-hours", type=float, default=6)
    parser.add_argument("--reset-margin-sec", type=float, default=120)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    cfg = parse_args(argv)
    prompt = cfg.prompt_file.read_text()
    log_dir = cfg.repo / "logs" / "overnight"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    iteration = stalls = limit_streak = 0
    previous_head = git_head(cfg.repo)

    while iteration < cfg.max_iterations:
        iteration += 1
        print(f"=== iteration {iteration} ===", flush=True)
        log_path = log_dir / f"{stamp}-iter{iteration:02d}.jsonl"
        summary = run_iteration(cfg, prompt, log_path)
        print(
            f"  finished (model {summary.model}, exit {summary.returncode}, "
            f"${summary.cost_usd:.2f}, {usage_text(summary)}); log: {log_path}",
            flush=True,
        )

        if is_done(cfg.repo):
            print("PROGRESS.md marked DONE, stopping.")
            return 0

        if summary.limit_hit:
            iteration -= 1
            limit_streak += 1
            if limit_streak >= MAX_LIMIT_STREAK:
                print(f"Hit the usage limit {limit_streak} times in a row, stopping.")
                return 3
        else:
            limit_streak = 0
            head = git_head(cfg.repo)
            stalls = stalls + 1 if head == previous_head else 0
            previous_head = head
            if summary.returncode != 0:
                time.sleep(30)
            if stalls >= cfg.stall_limit:
                print(f"No commits in {cfg.stall_limit} iterations, stopping (stuck).")
                return 1

        action = decide(summary, cfg, time.time())
        if action.kind == "stop":
            print(f"Stopping: {action.reason}.")
            return 3
        if action.kind == "wait":
            resume = datetime.fromtimestamp(action.until).strftime("%Y-%m-%d %H:%M")
            print(f"Waiting until {resume}: {action.reason}.", flush=True)
            sleep_until(action.until)

    print(f"Reached the cap of {cfg.max_iterations} iterations.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
