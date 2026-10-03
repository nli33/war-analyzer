import json
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import overnight  # noqa: E402

# A rate_limit_event captured from a real `claude -p ... --output-format stream-json --verbose` run.
REAL_RATE_LIMIT_EVENT = {
    "type": "rate_limit_event",
    "rate_limit_info": {
        "status": "allowed",
        "resetsAt": 1790927400,
        "rateLimitType": "five_hour",
        "overageStatus": "rejected",
        "isUsingOverage": False,
        "unifiedWindows": {
            "five_hour": {"utilization": 0.01, "resetsAt": 1790927400},
            "seven_day": {"utilization": 0.21, "resetsAt": 1791158400},
        },
    },
}


def make_cfg(**overrides):
    values = dict(min_remaining_pct=None, wait_for_reset=False, max_wait_hours=6, reset_margin_sec=0)
    values.update(overrides)
    return Namespace(**values)


def summary_with(five_used=0.1, seven_used=0.1, five_reset=1000, seven_reset=900_000):
    summary = overnight.RunSummary()
    summary.five_hour = overnight.Window(five_used, five_reset)
    summary.seven_day = overnight.Window(seven_used, seven_reset)
    return summary


def test_parses_real_rate_limit_event():
    summary = overnight.RunSummary()
    overnight.update_summary(summary, REAL_RATE_LIMIT_EVENT)
    assert summary.status == "allowed"
    assert summary.five_hour.utilization == 0.01
    assert summary.five_hour.remaining_pct == pytest.approx(99)
    assert summary.seven_day.resets_at == 1791158400
    assert not summary.limit_hit


def test_continues_when_plenty_of_usage_left():
    action = overnight.decide(summary_with(five_used=0.5), make_cfg(min_remaining_pct=10), now=0)
    assert action.kind == "continue"


def test_no_threshold_never_stops_on_usage():
    action = overnight.decide(summary_with(five_used=0.99), make_cfg(), now=0)
    assert action.kind == "continue"


def test_stops_when_five_hour_window_nearly_used():
    action = overnight.decide(summary_with(five_used=0.95), make_cfg(min_remaining_pct=10), now=0)
    assert action.kind == "stop"
    assert "five-hour" in action.reason


def test_waits_for_five_hour_reset_when_enabled():
    cfg = make_cfg(min_remaining_pct=10, wait_for_reset=True, reset_margin_sec=120)
    action = overnight.decide(summary_with(five_used=0.95, five_reset=5000), cfg, now=1000)
    assert action.kind == "wait"
    assert action.until == 5120


def test_stops_instead_of_waiting_days_for_the_weekly_window():
    cfg = make_cfg(min_remaining_pct=10, wait_for_reset=True)
    summary = summary_with(seven_used=0.97, seven_reset=1000 + 3 * 86400)
    assert overnight.decide(summary, cfg, now=1000).kind == "stop"


def test_both_windows_low_waits_for_the_later_reset_or_stops():
    cfg = make_cfg(min_remaining_pct=10, wait_for_reset=True)
    soon = summary_with(five_used=0.95, seven_used=0.95, five_reset=2000, seven_reset=3000)
    assert overnight.decide(soon, cfg, now=1000).until == 3000
    far = summary_with(five_used=0.95, seven_used=0.95, five_reset=2000, seven_reset=1000 + 86400)
    assert overnight.decide(far, cfg, now=1000).kind == "stop"


def test_limit_hit_detected_from_status_and_from_error_text():
    by_status = overnight.RunSummary()
    overnight.update_summary(by_status, {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": 777}})
    assert by_status.limit_hit and by_status.reset_at == 777

    by_text = overnight.RunSummary()
    overnight.update_summary(by_text, {"type": "result", "is_error": True, "result": "Claude AI usage limit reached|1790927400"})
    assert by_text.limit_hit and by_text.reset_at == 1790927400

    ordinary_error = overnight.RunSummary()
    overnight.update_summary(ordinary_error, {"type": "result", "is_error": True, "result": "tool crashed"})
    assert not ordinary_error.limit_hit


def test_limit_hit_without_known_reset_time_stops():
    summary = overnight.RunSummary(status="rejected")
    action = overnight.decide(summary, make_cfg(wait_for_reset=True), now=0)
    assert action.kind == "stop"


def test_network_error_detected_from_result_text():
    for text in ["API Error: Can't reach the API server — check your internet or DNS (EAI_AGAIN)", "API Error: Connection dropped (ECONNRESET)"]:
        summary = overnight.RunSummary()
        overnight.update_summary(summary, {"type": "result", "is_error": True, "result": text})
        assert summary.network_error and not summary.limit_hit
    ordinary = overnight.RunSummary()
    overnight.update_summary(ordinary, {"type": "result", "is_error": True, "result": "tool crashed"})
    assert not ordinary.network_error


def test_network_backoff_doubles_and_caps():
    assert [overnight.network_backoff_sec(n) for n in (1, 2, 3)] == [60, 120, 240]
    assert overnight.network_backoff_sec(20) == 1800


# --- end-to-end with a stand-in for the claude CLI --------------------------------------------

STUB = """#!{python}
import json, subprocess, sys, time
from pathlib import Path

repo = Path.cwd()
counter = repo.parent / (repo.name + ".calls")
calls = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(calls))
scenario = json.loads((repo.parent / (repo.name + ".scenario.json")).read_text())[calls - 1]

def emit(event):
    print(json.dumps(event), flush=True)

emit({{"type": "system", "subtype": "init", "model": "stub-model"}})
if scenario.get("network_error"):
    emit({{"type": "result", "is_error": True, "result": "API Error: Connection dropped (ECONNRESET)"}})
    sys.exit(1)
if scenario.get("limit_hit"):
    emit({{"type": "rate_limit_event", "rate_limit_info": {{"status": "rejected", "resetsAt": int(time.time()) + 1}}}})
    emit({{"type": "result", "is_error": True, "result": "usage limit reached"}})
    sys.exit(1)

reset = int(time.time()) + scenario.get("reset_in", 3600)
emit({{"type": "rate_limit_event", "rate_limit_info": {{"status": "allowed", "unifiedWindows": {{
    "five_hour": {{"utilization": scenario["used"], "resetsAt": reset}},
    "seven_day": {{"utilization": 0.1, "resetsAt": reset + 400000}}}}}}}})
if scenario.get("done"):
    (repo / "PROGRESS.md").write_text("done\\nDONE\\n")
if scenario.get("blocked"):
    (repo / "PROGRESS.md").write_text("BLOCKED: needs a decision\\n")
(repo / f"work{{calls}}.txt").write_text("x")
if scenario.get("commit", True):
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"feat: task {{calls}}"], check=True)
emit({{"type": "result", "is_error": False, "result": "ok", "total_cost_usd": 0.01}})
"""


@pytest.fixture
def fake_repo(tmp_path):
    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q")
    (tmp_path / "PROGRESS.md").write_text("- [ ] task\n")
    (tmp_path / "prompt.txt").write_text("do the next task")
    stub = tmp_path / "claude_stub.py"
    stub.write_text(STUB.format(python=sys.executable))
    stub.chmod(0o755)
    run("add", "-A")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return tmp_path


def run_loop(repo, scenario, *flags):
    (repo.parent / (repo.name + ".scenario.json")).write_text(json.dumps(scenario))
    return overnight.main([
        "--repo", str(repo),
        "--prompt-file", str(repo / "prompt.txt"),
        "--claude-bin", str(repo / "claude_stub.py"),
        "--reset-margin-sec", "0",
        *flags,
    ])


def commit_count(repo):
    out = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    return int(out.stdout)


def test_loop_finishes_the_task_then_stops_when_usage_is_low(fake_repo):
    code = run_loop(fake_repo, [{"used": 0.95}, {"used": 0.1, "done": True}], "--min-remaining-pct", "10")
    assert code == 3
    assert commit_count(fake_repo) == 2  # init plus the one finished task, nothing started after it


def test_loop_waits_for_reset_then_resumes_and_finishes(fake_repo):
    scenario = [{"used": 0.95, "reset_in": 2}, {"used": 0.1, "done": True}]
    started = time.time()
    code = run_loop(fake_repo, scenario, "--min-remaining-pct", "10", "--wait-for-reset")
    assert code == 0
    assert time.time() - started >= 1
    assert commit_count(fake_repo) == 3


def test_limit_hit_mid_task_is_not_a_stall_and_retries_after_reset(fake_repo):
    scenario = [{"limit_hit": True}, {"used": 0.1, "done": True}]
    code = run_loop(fake_repo, scenario, "--wait-for-reset", "--stall-limit", "1")
    assert code == 0
    assert commit_count(fake_repo) == 2


def test_limit_hit_without_wait_flag_stops(fake_repo):
    code = run_loop(fake_repo, [{"limit_hit": True}])
    assert code == 3


def test_uncommitted_changes_count_as_progress_not_a_stall(fake_repo):
    scenario = [{"used": 0.1, "commit": False}] * 3 + [{"used": 0.1, "done": True}]
    code = run_loop(fake_repo, scenario, "--stall-limit", "2")
    assert code == 0


def test_blocked_line_stops_the_loop_after_that_iteration(fake_repo):
    code = run_loop(fake_repo, [{"used": 0.1, "blocked": True}, {"used": 0.1, "done": True}])
    assert code == 4
    assert commit_count(fake_repo) == 2  # the blocked iteration ran, nothing after it


def test_existing_blocked_line_refuses_to_start(fake_repo):
    (fake_repo / "PROGRESS.md").write_text("BLOCKED: left over\n")
    code = run_loop(fake_repo, [{"used": 0.1, "done": True}])
    assert code == 4
    assert not (fake_repo.parent / (fake_repo.name + ".calls")).exists()


def test_unchanged_repo_counts_as_stall(fake_repo):
    (fake_repo / "claude_stub.py").write_text("#!/bin/sh\necho '{\"type\":\"result\",\"is_error\":false,\"result\":\"nothing\"}'\n")
    code = overnight.main([
        "--repo", str(fake_repo), "--prompt-file", str(fake_repo / "prompt.txt"),
        "--claude-bin", str(fake_repo / "claude_stub.py"), "--stall-limit", "2",
    ])
    assert code == 1


def test_network_errors_are_not_stalls_and_loop_recovers(fake_repo, monkeypatch):
    monkeypatch.setattr(overnight.time, "sleep", lambda seconds: None)
    scenario = [{"network_error": True}] * 4 + [{"used": 0.1, "done": True}]
    code = run_loop(fake_repo, scenario, "--stall-limit", "1")
    assert code == 0


def test_network_errors_in_a_row_eventually_stop(fake_repo, monkeypatch):
    monkeypatch.setattr(overnight.time, "sleep", lambda seconds: None)
    code = run_loop(fake_repo, [{"network_error": True}] * overnight.MAX_NETWORK_STREAK)
    assert code == 5
