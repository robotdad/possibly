"""Atomic retained state, receipts and ordered observations in a host-selected SQLite store."""

import contextlib
import json
import sqlite3
import time
import uuid
from pathlib import Path

from .models import PossiblyError


def new_id(prefix):
    return prefix + "_" + uuid.uuid4().hex


def event(state, kind, **data):
    state["state_version"] += 1
    state["events"].append(
        {
            "cursor": len(state["events"]) + 1,
            "kind": kind,
            "exploration_id": state["id"],
            "state_version": state["state_version"],
            "time": time.time(),
            **data,
        }
    )


class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "possibly.sqlite3"
        with self.connect() as db:
            db.executescript("""
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS explorations(id TEXT PRIMARY KEY, body TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS receipts(caller TEXT, request TEXT, payload TEXT, receipt TEXT,
                PRIMARY KEY(caller, request));
            """)
        self.path.chmod(0o600)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        return db

    @contextlib.contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, eid, db=None):
        if db is None:
            with self.connect() as conn:
                return self.get(eid, conn)
        row = db.execute("SELECT body FROM explorations WHERE id=?", (eid,)).fetchone()
        if row is None:
            raise PossiblyError("not_found", f"Exploration {eid!r} does not exist.", "Use an ID from start.")
        return json.loads(row[0])

    def put(self, db, state):
        db.execute("INSERT OR REPLACE INTO explorations VALUES (?,?)", (state["id"], json.dumps(state)))

    def mutate(self, caller, request_id, payload, fn):
        if not request_id or len(request_id) > 200:
            raise PossiblyError(
                "invalid_request_id", "Supply a nonempty request_id of at most 200 characters."
            )
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self.transaction() as db:
            row = db.execute(
                "SELECT payload,receipt FROM receipts WHERE caller=? AND request=?", (caller, request_id)
            ).fetchone()
            if row:
                if row[0] != encoded:
                    raise PossiblyError(
                        "request_conflict",
                        "This request ID was used with different inputs.",
                        "Retry the original inputs or use a new request ID.",
                    )
                return {"status": "replayed", "receipt": json.loads(row[1])}
            receipt = fn(db)
            db.execute(
                "INSERT INTO receipts VALUES (?,?,?,?)", (caller, request_id, encoded, json.dumps(receipt))
            )
            return {"status": "accepted", "receipt": receipt}
