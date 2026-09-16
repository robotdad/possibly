"""Explicitly owned subprocess runner and loopback-only presentation adapter."""

import argparse
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .models import PossiblyError
from .store import event, new_id


def write_access_token(root, runner_id):
    """Keep presenter credentials in a private live-resource file, outside retained records."""
    token = secrets.token_urlsafe(32)
    path = Path(root) / (runner_id + ".token")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(token)
    return token


def viewer_url(root, runner):
    if not runner or not runner.get("url"):
        return None
    try:
        token = (Path(root) / (runner["id"] + ".token")).read_text()
    except FileNotFoundError:
        return None
    return runner["url"] + "#" + token


def runner_environment(adapter):
    config = adapter.configuration()
    child_env = dict(os.environ)
    child_env.update(
        POSSIBLY_PROVIDER=config.provider,
        POSSIBLY_MODEL=config.model or "",
        POSSIBLY_REASONING_EFFORT=config.effort or "",
        POSSIBLY_PROVIDER_CONFIG=json.dumps(config.options),
    )
    if not (adapter.provider or adapter._config or os.environ.get("POSSIBLY_PROVIDER")):
        child_env.pop("POSSIBLY_PROVIDER", None)
    return child_env


def launch(client, eid):
    with client.store.transaction() as db:
        state = client.store.get(eid, db)
        if state.get("runner") and state["runner"].get("state") != "closed":
            runner = state["runner"]
            if time.time() - runner.get("heartbeat", 0) < 10:
                return {"status": "available", "url": viewer_url(client.store.root, runner)}
            raise PossiblyError(
                "runner_interrupted",
                "Previous runner stopped responding.",
                "Inspect operation state before authorizing recovery; do not replay blindly.",
            )
        runner = {
            "id": new_id("runner"),
            "state": "starting",
            "heartbeat": time.time(),
            "period": state["active_period_id"],
            "url": None,
        }
        write_access_token(client.store.root, runner["id"])
        state["runner"] = runner
        client.store.put(db, state)
    argv = [sys.executable, "-m", "possibly.runner", "--store", str(client.store.root), "--exploration", eid]
    child_env = runner_environment(client.intelligence)
    log = client.store.root / (runner["id"] + ".log")
    with log.open("ab") as stream:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            start_new_session=True,
            env=child_env,
        )
    with client.store.transaction() as db:
        state = client.store.get(eid, db)
        state["runner"]["pid"] = process.pid
        client.store.put(db, state)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = client.store.get(eid)["runner"]
        if current["state"] == "ready":
            return {"status": "available", "url": viewer_url(client.store.root, current)}
        time.sleep(0.05)
    return {"status": "starting", "remedy": "Read exploration status for runner readiness.", "log": str(log)}


def serve(client, eid):
    """Serve only this exploration. Tokens are never sent to generated iframe documents."""
    initial = client.store.get(eid)
    runner = initial["runner"]
    token = (client.store.root / (runner["id"] + ".token")).read_text()
    period = initial["active_period_id"]
    server = None
    presentation_attempted = False
    provider_job = {"status": "idle", "messages": []}
    provider_job_lock = threading.Lock()

    def run_provider_job(kind, data):
        def progress(message):
            with provider_job_lock:
                provider_job["messages"].append(str(message))

        try:
            result = (
                client.provider_login(**data, on_progress=progress)
                if kind == "login"
                else client.provider_models(**data)
                if kind == "models"
                else client.test_provider(**data)
            )
            with provider_job_lock:
                provider_job.update(status="complete", result=result)
        except PossiblyError as exc:
            with provider_job_lock:
                provider_job.update(status="failed", error=exc.to_dict()["error"])
        except Exception:
            with provider_job_lock:
                provider_job.update(
                    status="failed", error={"message": "Provider action failed. Check setup and try again."}
                )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, value, code=200, content_type="application/json"):
            body = value.encode() if isinstance(value, str) else json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token)

        def do_GET(self):
            if self.path == "/":
                return self.send(
                    Path(__file__).with_name("dashboard.html").read_text(), content_type="text/html"
                )
            if not self.authorized():
                return self.send({"error": "unauthorized"}, 401)
            if self.path == "/settings":
                return self.send(client.provider_settings())
            if self.path == "/provider-job":
                with provider_job_lock:
                    return self.send(dict(provider_job))
            if self.path == "/progress":
                snapshot = client.get_exploration(eid)
                return self.send(
                    [
                        client.operation_diagnostics(eid, o["id"])
                        for o in snapshot["operations"].values()
                        if o["kind"] == "explore"
                    ]
                )
            if self.path == "/state":
                snapshot = client.get_exploration(eid)
                # Public library access also supplies artifact content, no private browser-only capability.
                for rid, revision in snapshot["revisions"].items():
                    revision["html"] = client.read_artifact(eid, rid)
                return self.send(snapshot)
            return self.send({"error": "not_found"}, 404)

        def do_POST(self):
            if not self.authorized():
                return self.send({"error": "unauthorized"}, 401)
            origin = self.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{server.server_port}":
                return self.send({"error": "invalid_origin"}, 403)
            if client.store.get(eid)["active_period_id"] != period:
                return self.send({"error": "stale_viewer"}, 409)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length < 100_000:
                    return self.send({"error": "invalid_body"}, 400)
                data = json.loads(self.rfile.read(length))
                if self.path == "/settings":
                    if any(
                        o["state"] in {"queued", "running"}
                        for o in client.store.get(eid)["operations"].values()
                    ):
                        raise PossiblyError("provider_busy", "Wait for generation before changing providers.")
                    result = client.configure_provider(**data)
                elif self.path == "/provider-job":
                    if any(
                        o["state"] in {"queued", "running"}
                        for o in client.store.get(eid)["operations"].values()
                    ):
                        raise PossiblyError(
                            "provider_busy", "Wait for generation before testing or signing in."
                        )
                    kind = data.pop("kind", "test")
                    if kind not in {"test", "login", "models"} or set(data) - {
                        "provider",
                        "model",
                        "reasoning_effort",
                        "provider_config",
                        "timeout_seconds",
                    }:
                        raise PossiblyError("invalid_settings", "Unknown provider action or option.")
                    if kind in {"login", "models"} and set(data) - {"provider", "timeout_seconds"}:
                        raise PossiblyError("invalid_settings", "Login accepts only provider and timeout.")
                    with provider_job_lock:
                        if provider_job["status"] == "running":
                            raise PossiblyError("provider_busy", "A provider action is already running.")
                        provider_job.clear()
                        provider_job.update(status="running", kind=kind, messages=[])
                    threading.Thread(target=run_provider_job, args=(kind, data), daemon=True).start()
                    result = {"status": "running"}
                elif self.path == "/decision":
                    result = client.record_decision(
                        eid,
                        data["revision_id"],
                        action=data["action"],
                        text=data.get("text", ""),
                        request_id=data["request_id"],
                        expected_state_version=data["expected_state_version"],
                    )
                elif self.path == "/review-state":
                    result = client.save_review_state(eid, **data)
                elif self.path == "/export":
                    result = client.export(eid, data["revision_id"], request_id=data["request_id"])
                elif self.path == "/answer":
                    # The worker, not the HTTP handler, drives continuation.
                    from .lib import Possibly

                    observer = Possibly(client.store.root, caller="dashboard")
                    result = observer.answer(
                        eid,
                        data["operation_id"],
                        data["question_id"],
                        data["text"],
                        request_id=data["request_id"],
                    )
                else:
                    return self.send({"error": "not_found"}, 404)
                self.send(result)
            except PossiblyError as exc:
                self.send(exc.to_dict(), 409)
            except (ValueError, KeyError, TypeError):
                self.send({"error": "invalid_request"}, 400)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = None
        active_operation = None
        try:
            while True:
                state = client.store.get(eid)
                if state["lifecycle"] != "active" or state["active_period_id"] != period:
                    break
                # Builtin dashboard becomes available automatically when there is material or a question.
                presentable = (
                    bool(state.get("exploration_plan"))
                    or bool(state["revisions"])
                    or any(o["state"] == "waiting_input" for o in state["operations"].values())
                )
                if not presentation_attempted and state["presentation"]["mode"] == "builtin" and presentable:
                    presentation_attempted = True
                    try:
                        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                    except OSError:
                        with client.store.transaction() as db:
                            s = client.store.get(eid, db)
                            event(
                                s,
                                "presentation_failed",
                                remedy="Read artifacts through the library or host UI.",
                            )
                            client.store.put(db, s)
                        continue
                    server.timeout = 0.1
                    url = f"http://127.0.0.1:{server.server_port}/"
                    with client.store.transaction() as db:
                        s = client.store.get(eid, db)
                        s["runner"]["url"] = url
                        event(s, "presentation_available", url=url)
                        client.store.put(db, s)
                    if state["presentation"]["open_viewer"]:
                        import webbrowser

                        opened = webbrowser.open(url + "#" + token)
                        with client.store.transaction() as db:
                            s = client.store.get(eid, db)
                            event(s, "viewer_open_requested" if opened else "viewer_open_failed")
                            client.store.put(db, s)
                if server:
                    server.handle_request()
                else:
                    time.sleep(0.1)
                if future is not None and future.done():
                    try:
                        future.result()
                    except PossiblyError as exc:
                        with client.store.transaction() as db:
                            s = client.store.get(eid, db)
                            operation = s["operations"].get(active_operation)
                            if operation and operation["state"] == "queued" and exc.code != "operation_busy":
                                operation["state"] = "failed"
                                operation["failure"] = exc.to_dict()["error"]
                                event(s, "operation_failed", operation_id=active_operation)
                                client.store.put(db, s)
                    future = None
                if future is None:
                    pending = next((o for o in state["operations"].values() if o["state"] == "queued"), None)
                    if pending:
                        active_operation = pending["id"]
                        future = pool.submit(client.run_operation, eid, active_operation)
                with client.store.transaction() as db:
                    s = client.store.get(eid, db)
                    s["runner"].update(state="ready", heartbeat=time.time())
                    client.store.put(db, s)
        finally:
            if server:
                server.server_close()
            if future:
                try:
                    future.result(timeout=10)
                except TimeoutError:
                    # Do not acknowledge cleanup until the actual execution thread exits.
                    future.result()
                except Exception:
                    pass
            (client.store.root / (runner["id"] + ".token")).unlink(missing_ok=True)
            with client.store.transaction() as db:
                s = client.store.get(eid, db)
                s["runner"]["state"] = "closed"
                s["runner"]["url"] = None
                event(s, "runner_closed", resource_id=runner["id"])
                client.store.put(db, s)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", required=True)
    parser.add_argument("--exploration", required=True)
    parser.add_argument("--provider")
    parser.add_argument("--model")
    args = parser.parse_args()
    from .intelligence import AmplifierIntelligence
    from .lib import Possibly

    client = Possibly(
        args.store,
        intelligence=AmplifierIntelligence(provider=args.provider, model=args.model, allow_environment=True),
        caller="dashboard",
        execution="owned_runner",
    )
    serve(client, args.exploration)


if __name__ == "__main__":
    main()
