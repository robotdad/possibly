"""Inspect and stop owned workers without platform-specific liveness signals."""

import os
import signal
import subprocess

import psutil


def is_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True


def stop_tree(process):
    """Stop a verified worker and its descendants, guarding against PID reuse."""
    if process.pid == os.getpid():
        raise ValueError("Cannot stop the calling process")
    try:
        if not process.is_running():
            return
        if os.name != "nt" and os.getpgid(process.pid) == process.pid:
            os.killpg(process.pid, signal.SIGKILL)
            return
        # Freeze the producer before collecting children so it cannot start more work.
        process.suspend()
        try:
            children = process.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            process.kill()
        except Exception:
            try:
                process.resume()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            raise
        _, alive = psutil.wait_procs([*children, process], timeout=10)
        if alive:
            raise TimeoutError("Owned worker processes did not stop")
    except (psutil.NoSuchProcess, ProcessLookupError):
        pass


def stop_worker(process):
    if process is None or process.poll() is not None:
        return
    try:
        worker = psutil.Process(process.pid)
        if os.name != "nt":
            children = worker.children(recursive=True)
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            # A leader can exit before its children. Use their captured identities,
            # rather than signalling a now-empty or reaped process group again.
            for child in children:
                try:
                    if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                        child.kill()
                except psutil.NoSuchProcess:
                    pass
        else:
            stop_tree(worker)
    except (psutil.NoSuchProcess, ProcessLookupError):
        pass
    process.wait(timeout=10)
