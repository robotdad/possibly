"""Public request types and structured errors; responses are JSON-compatible dictionaries."""

from dataclasses import asdict, dataclass
from typing import Literal


class PossiblyError(Exception):
    def __init__(self, code: str, message: str, remedy: str = "", **details):
        super().__init__(message)
        self.code, self.message, self.remedy, self.details = code, message, remedy, details

    def to_dict(self):
        return {
            "status": "rejected",
            "error": {"code": self.code, "message": self.message, "remedy": self.remedy, **self.details},
        }


@dataclass(frozen=True)
class Grant:
    """Authority for one operation, plus at most one prototype after selection.

    max_turns bounds engine submissions including answers and repair attempts;
    timeout_seconds bounds cumulative execution time, including preparation/tools.
    max_tool_calls bounds tool executions in each engine submission.
    max_model_calls bounds provider requests, including visual feedback, per submission.
    Provider-internal HTTP retries remain subject to the overall timeout.
    """

    actions: tuple[str, ...] = ("explore",)
    max_turns: int = 4
    timeout_seconds: int = 300
    max_tool_calls: int = 20
    max_model_calls: int = 12
    prototype_after_selection: bool = False
    expires_at: float | None = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Presentation:
    mode: Literal["headless", "host", "builtin"] = "headless"
    service: bool = False
    open_viewer: bool = False

    def to_dict(self):
        return asdict(self)
