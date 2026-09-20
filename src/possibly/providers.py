"""Runtime-only provider configuration. Native credentials never enter retained state."""

import asyncio
import copy
import importlib
import json
import os
import sys
import time
from dataclasses import dataclass, field

from .models import PossiblyError

COPILOT_ENV = ("COPILOT_AGENT_TOKEN", "COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")


def catalog():
    from amplifier_agent_cli.provider_sources import PROVIDER_CATALOG

    return PROVIDER_CATALOG


def checked_config(value):
    """Validate non-secret provider options consistently for every public adapter."""
    if not isinstance(value, dict):
        raise PossiblyError("invalid_settings", "Provider config must be a JSON object.")

    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (ValueError, TypeError):
        raise PossiblyError("invalid_settings", "Provider config must contain JSON values.") from None
    if len(encoded) > 8_000:
        raise PossiblyError("invalid_settings", "Provider config must be at most 8 KB of JSON.")

    def check(obj, depth=0):
        if depth > 4:
            raise PossiblyError("invalid_settings", "Provider config may be nested at most four levels.")
        if isinstance(obj, dict):
            if len(obj) > 32:
                raise PossiblyError(
                    "invalid_settings", "Provider config objects may contain at most 32 fields."
                )
            for key, item in obj.items():
                if not isinstance(key, str) or len(key) > 100:
                    raise PossiblyError(
                        "invalid_settings", "Provider option names must be strings of at most 100 characters."
                    )
                if key.lower() in {"token", "auth_token", "headers", "extra_headers"} or any(
                    word in key.lower().replace("-", "_")
                    for word in (
                        "api_key",
                        "password",
                        "secret",
                        "credential",
                        "authorization",
                        "access_token",
                        "refresh_token",
                    )
                ):
                    raise PossiblyError(
                        "invalid_settings",
                        "Use native environment variables for credentials, not provider config.",
                    )
                check(item, depth + 1)
        elif isinstance(obj, list):
            if len(obj) > 32:
                raise PossiblyError("invalid_settings", "Provider config lists may contain at most 32 items.")
            for item in obj:
                check(item, depth + 1)
        elif not isinstance(obj, (str, int, float, bool, type(None))):
            raise PossiblyError("invalid_settings", "Provider config must contain JSON scalar values.")

    check(value)
    return copy.deepcopy(value)


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str | None = None
    effort: str | None = None
    options: dict = field(default_factory=dict)

    @classmethod
    def resolve(cls, provider=None, model=None, effort=None, provider_config=None):
        try:
            options = checked_config(
                provider_config
                if provider_config is not None
                else json.loads(os.environ.get("POSSIBLY_PROVIDER_CONFIG", "{}"))
            )
        except (ValueError, TypeError):
            raise PossiblyError(
                "invalid_settings", "POSSIBLY_PROVIDER_CONFIG must be a JSON object."
            ) from None
        name = provider or os.environ.get("POSSIBLY_PROVIDER") or "openai"
        if not isinstance(name, str) or name not in catalog():
            raise PossiblyError("unknown_provider", "Unknown provider. Choose a name from provider-settings.")
        return cls(
            name,
            model if model is not None else os.environ.get("POSSIBLY_MODEL") or None,
            effort if effort is not None else os.environ.get("POSSIBLY_REASONING_EFFORT") or None,
            options,
        )

    def public(self):
        return {
            "provider": self.provider,
            "model": self.model,
            "reasoning_effort": self.effort,
            "configured_fields": sorted(self.options),
            "storage": "process memory; environment defaults",
        }

    def entry(self, *, require=True):
        from amplifier_agent_cli.provider_sources import build_provider_entry

        status = credential_status(self.provider)
        endpoint = self.options.get("base_url") or self.options.get("host")
        if (
            require
            and not status["configured"]
            and not (self.provider in {"ollama", "vllm", "chat-completions"} and endpoint)
        ):
            raise PossiblyError(
                "provider_unavailable",
                f"{self.provider} needs environment credentials or provider login.",
                "Run provider-settings for setup instructions.",
            )
        entry = build_provider_entry(self.provider)
        # API-key configuration is env-only. Provider-owned OAuth caches are allowed.
        if status["source"] != "env" and self.provider != "openai-chatgpt":
            entry["config"] = {
                k: v for k, v in entry["config"].items() if k in {"priority", "rate_limit_state_path"}
            }
        entry["config"].update(self.options)
        if self.provider == "github-copilot":
            for key in COPILOT_ENV:
                if os.environ.get(key):
                    entry["config"]["api_key"] = os.environ[key]
                    break
        if self.model:
            entry["config"]["default_model"] = self.model
        if self.effort:
            entry["config"]["reasoning_effort"] = self.effort
        # No surprise interactive authentication inside generation or connection tests.
        if self.provider == "openai-chatgpt":
            entry["config"]["login_on_mount"] = False
        return entry


def credential_status(name):
    from amplifier_agent_cli.provider_sources import resolve_credential_detailed

    if name == "github-copilot":
        env = next((key for key in COPILOT_ENV if os.environ.get(key)), None)
        return {"configured": bool(env), "source": "env" if env else "none", "env_var": env}
    resolution = resolve_credential_detailed(name)
    accepted = resolution.source == "env" or name == "openai-chatgpt" and resolution.resolved
    return {
        "configured": bool(accepted and resolution.resolved),
        "source": resolution.source if accepted else "none",
        "env_var": resolution.env_var,
    }


def settings(config):
    return {
        "effective": config.public(),
        "providers": [{"name": name, **credential_status(name), "setup": setup(name)} for name in catalog()],
    }


def setup(name):
    from amplifier_agent_cli.provider_sources import PROVIDER_CREDENTIAL_VARS

    if name == "openai-chatgpt":
        return "Use provider-login (or Sign in in the dashboard). Complete the device flow; tokens stay in the provider OAuth cache."
    if name == "github-copilot":
        return 'Use gh auth login, then export GH_TOKEN="$(gh auth token)" before starting Possibly. An account with Copilot access is required.'
    if name == "chat-completions":
        return "Set CHAT_COMPLETIONS_BASE_URL and optionally CHAT_COMPLETIONS_API_KEY; choose a model."
    if name == "vllm":
        return "Set VLLM_BASE_URL and optionally VLLM_API_KEY; choose a model."
    return (
        "Configure "
        + ", ".join(PROVIDER_CREDENTIAL_VARS.get(name, ()))
        + (" and AZURE_OPENAI_ENDPOINT; model is the deployment name." if name == "azure-openai" else ".")
    )


async def prepared_for(config, *, require=True):
    from amplifier_agent_lib import __version__
    from amplifier_agent_lib.bundle.cache import load_and_prepare_cached

    prepared = copy.copy(await load_and_prepare_cached(aaa_version=__version__))
    prepared.mount_plan = copy.deepcopy(prepared.mount_plan)
    prepared.mount_plan.update(providers=[config.entry(require=require)], tools=[], agents={}, hooks=[])
    return prepared


async def connection_test(config, timeout_seconds):
    from amplifier_core.message_models import ChatRequest, Message

    started = time.monotonic()

    async def run():
        prepared = await prepared_for(config)
        await refresh_auth(prepared, config)
        session = await prepared.create_session()
        async with session:
            await ensure_provider(session, config)
            providers = session.coordinator.get("providers")
            provider = next(iter(providers.values()))
            request = ChatRequest(
                messages=[Message(role="user", content="Reply with OK only.")],
                model=config.model,
                max_output_tokens=64,
                timeout=timeout_seconds,
            )
            request_started = time.monotonic()
            response = await provider.complete(request)
            usage = getattr(response, "usage", None)
            if hasattr(usage, "model_dump"):
                usage = usage.model_dump()
            return {
                "status": "succeeded",
                "provider": config.provider,
                "model": config.model or getattr(provider, "default_model", None),
                "seconds": round(time.monotonic() - started, 3),
                "startup_seconds": round(request_started - started, 3),
                "request_seconds": round(time.monotonic() - request_started, 3),
                "usage": {k: v for k, v in (usage or {}).items() if isinstance(v, (int, float))},
            }

    try:
        return await asyncio.wait_for(run(), timeout_seconds)
    except PossiblyError:
        raise
    except Exception as exc:
        # Provider errors can contain request URLs, headers, or raw credentials.
        raise PossiblyError(
            "provider_test_failed",
            f"{config.provider} connection test failed ({type(exc).__name__}).",
            "Check credentials, provider access, model and endpoint; no fallback provider was used.",
        ) from None


async def login(config, timeout_seconds, progress):
    if config.provider == "github-copilot":
        # Explicit login only: gh owns device authorization and its credential cache.
        async def command(*args, stream=False):
            proc = await asyncio.create_subprocess_exec(
                "gh",
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT if stream else asyncio.subprocess.DEVNULL,
                env={**os.environ, "GH_BROWSER": "echo"},
            )
            try:
                if stream:
                    async for line in proc.stdout:
                        progress(line.decode(errors="replace").rstrip())
                    return await proc.wait(), b""
                output, _ = await proc.communicate()
                return proc.returncode, output
            except BaseException:
                if proc.returncode is None:
                    proc.terminate()
                await proc.wait()
                raise

        code, token = await command("auth", "token", "--hostname", "github.com")
        if code != 0:
            progress(
                "GitHub CLI will display a device code and verification URL. Complete authorization in your browser."
            )
            code, _ = await command("auth", "login", "--hostname", "github.com", "--web", stream=True)
            if code != 0:
                raise PossiblyError(
                    "provider_login_failed", "GitHub CLI login did not complete.", setup(config.provider)
                )
            code, token = await command("auth", "token", "--hostname", "github.com")
        if code or not token.strip():
            raise PossiblyError(
                "provider_login_failed", "GitHub CLI has no token available.", setup(config.provider)
            )
        os.environ["GH_TOKEN"] = token.decode().strip()
        return {
            "status": "succeeded",
            "provider": config.provider,
            "credential_storage": "GitHub CLI cache; token available in this process only",
            "instructions": setup(config.provider),
        }
    if config.provider != "openai-chatgpt":
        return {"status": "action_required", "instructions": setup(config.provider)}
    from amplifier_agent_cli.provider_sources import oauth_token_path

    # Resolve/install the module without mounting an unauthenticated provider.
    prepared = await prepared_for(config, require=False)
    oauth = await oauth_module(prepared)
    await asyncio.wait_for(
        oauth.login(token_file_path=str(oauth_token_path()), print_fn=progress), timeout_seconds
    )
    return {"status": "succeeded", "provider": config.provider, "credential_storage": "provider OAuth cache"}


async def ensure_provider(session, config):
    """Refresh provider-owned OAuth cache without starting interactive authentication."""
    if session.coordinator.get("providers"):
        return
    raise PossiblyError(
        "provider_unavailable", "The configured provider did not mount.", "Check provider setup."
    )


async def oauth_module(prepared):
    """Use Agent's source resolver to load auth helpers before provider validation."""
    entry = catalog()["openai-chatgpt"]
    source = await prepared.resolver.async_resolve(entry["module"], source_hint=entry["source"])
    path = str(source.resolve())
    if path not in sys.path:
        sys.path.insert(0, path)
    return importlib.import_module("amplifier_module_provider_openai_chatgpt.oauth")


async def refresh_auth(prepared, config):
    if config.provider != "openai-chatgpt":
        return
    oauth = await oauth_module(prepared)
    token_path = config.entry()["config"].get("token_file_path")
    tokens = oauth.load_tokens(token_path)
    if not oauth.is_token_valid(tokens) and tokens and tokens.get("refresh_token"):
        tokens = await oauth.refresh_tokens(tokens["refresh_token"], path=token_path)
    if not oauth.is_token_valid(tokens):
        raise PossiblyError(
            "provider_login_required",
            "ChatGPT login is missing or expired.",
            "Run provider-login explicitly.",
        )


async def discover_models(config, timeout_seconds):
    """Read the provider's model catalog; availability still requires a connection test."""

    async def run():
        prepared = await prepared_for(config)
        await refresh_auth(prepared, config)
        session = await prepared.create_session()
        async with session:
            await ensure_provider(session, config)
            provider = next(iter(session.coordinator.get("providers").values()))
            models = await provider.list_models()
            rows = []
            for model in models:
                data = model.model_dump() if hasattr(model, "model_dump") else model
                if isinstance(data, dict):
                    rows.append(
                        {
                            k: data[k]
                            for k in (
                                "id",
                                "display_name",
                                "context_window",
                                "max_output_tokens",
                                "capabilities",
                            )
                            if k in data
                        }
                    )
                else:
                    rows.append({"id": str(model)})
            return {
                "provider": config.provider,
                "default_model": getattr(provider, "default_model", None),
                "models": rows,
                "notice": "Provider catalog, not a guarantee of account access or tool/vision compatibility. Test the chosen model.",
            }

    try:
        return await asyncio.wait_for(run(), timeout_seconds)
    except PossiblyError:
        raise
    except Exception as exc:
        raise PossiblyError(
            "model_discovery_failed", f"Model discovery failed ({type(exc).__name__})."
        ) from None
