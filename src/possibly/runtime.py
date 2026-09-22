"""Provider boundary: screenshots, bounded calls, sanitized usage, and terminal submission."""

import time

from .checkpoints import digest
from .models import PossiblyError


class SubmissionComplete(BaseException):
    """Internal successful short-circuit; never converted to a provider/tool error."""


class ObservedProvider:
    def __init__(self, provider, candidates, diagnostics, limit):
        self.inner, self.candidates, self.diagnostics, self.limit = provider, candidates, diagnostics, limit

    def __getattr__(self, name):
        value = getattr(self.inner, name)
        if name == "stream":

            async def stream(request, **kwargs):
                request, shown, record = self.prepare(request)
                try:
                    async for chunk in value(request, **kwargs):
                        self.usage(record, chunk)
                        yield chunk
                    self.finish(record, shown)
                except BaseException as exc:
                    self.finish(record, {}, type(exc).__name__)
                    raise

            return stream
        return value

    def prepare(self, request):
        if self.candidates.runtime_failure is not None:
            raise self.candidates.runtime_failure
        if self.candidates.result is not None:
            raise SubmissionComplete()
        records = self.diagnostics.data["provider_calls"]
        if len(records) >= self.limit:
            self.candidates.runtime_failure = PossiblyError(
                "model_call_budget_exhausted", "The operation exhausted its model-call allowance."
            )
            raise self.candidates.runtime_failure
        from amplifier_core.message_models import Message

        content, shown = [], {}
        # Images are inserted after completed tool result messages, never mid-tool batch.
        for name, review in self.candidates.reviews.items():
            html = self.candidates.candidates[name]
            if review.get("artifact_hash") != digest(html):
                continue
            shown[name] = digest(html)
            content.extend(
                [
                    {
                        "type": "text",
                        "text": f"Current rendered candidate {name}. Review before submit_result.",
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": review.get("screenshot_media_type", "image/png"),
                            "data": review["screenshot_base64"],
                        },
                    },
                ]
            )
        if content:
            request = request.model_copy(
                update={"messages": [*request.messages, Message(role="user", content=content)]}
            )
        record = {
            "index": len(records) + 1,
            "started_at": time.time(),
            "status": "running",
            "model": request.model or getattr(self.inner, "default_model", None),
            "images": len(shown),
            "usage": {},
        }
        records.append(record)
        self.diagnostics.flush()
        return request, shown, record

    def usage(self, record, response):
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        if isinstance(usage, dict):
            record["usage"].update(
                {k: v for k, v in usage.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
            )

    def finish(self, record, shown, error=None):
        record.update(
            seconds=round(time.time() - record["started_at"], 4), status="failed" if error else "succeeded"
        )
        if error:
            record["error_type"] = error
        else:
            self.candidates.visual_seen.update(shown)
            self.candidates.checkpoint()
        totals = {}
        for call in self.diagnostics.data["provider_calls"]:
            for key, value in call.get("usage", {}).items():
                totals[key] = totals.get(key, 0) + value
        self.diagnostics.data["usage"] = totals
        self.diagnostics.flush()

    async def complete(self, request, **kwargs):
        request, shown, record = self.prepare(request)
        try:
            response = await self.inner.complete(request, **kwargs)
            self.usage(record, response)
            self.finish(record, shown)
            return response
        except BaseException as exc:
            self.finish(record, {}, type(exc).__name__)
            raise
