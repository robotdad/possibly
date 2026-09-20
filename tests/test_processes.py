"""Real process ownership, cancellation, and recovery checks on every OS."""

import subprocess
import sys
import time

import psutil

from possibly.processes import is_alive, stop_worker


def test_liveness_does_not_signal_live_process():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert is_alive(process.pid)
        assert process.poll() is None
        assert not is_alive(-1)
    finally:
        process.kill()
        process.wait(timeout=10)
    assert not is_alive(process.pid)


def test_stop_worker_stops_descendants(tmp_path):
    child_file = tmp_path / "child.txt"
    script = (
        "import subprocess, sys, time; from pathlib import Path; "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
    )
    process = subprocess.Popen([sys.executable, "-c", script, str(child_file)], start_new_session=True)
    child = None
    try:
        deadline = time.monotonic() + 10
        while not child_file.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        child = psutil.Process(int(child_file.read_text()))
        stop_worker(process)
        assert process.poll() is not None
        deadline = time.monotonic() + 10
        while is_alive(child.pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not is_alive(child.pid)
        stop_worker(process)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        if child:
            try:
                if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                    child.kill()
            except psutil.NoSuchProcess:
                pass
