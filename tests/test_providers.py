import asyncio
import json
from types import SimpleNamespace

import pytest

from possibly import PossiblyError
from possibly.intelligence import _ENGINE_LOCK, AmplifierIntelligence
from possibly.providers import ProviderConfig, checked_config, connection_test, credential_status


@pytest.fixture(autouse=True)
def settings_env(monkeypatch):
    import os

    for key in os.environ:
        if key.startswith("POSSIBLY_") or key in (
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "COPILOT_GITHUB_TOKEN",
            "COPILOT_AGENT_TOKEN",
        ):
            monkeypatch.delenv(key)


def test_defaults_precedence_and_no_provider_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-anthropic")
    assert ProviderConfig.resolve().provider == "openai"
    with pytest.raises(PossiblyError, match="openai needs"):
        ProviderConfig.resolve().entry()
    monkeypatch.setenv("POSSIBLY_PROVIDER", "anthropic")
    monkeypatch.setenv("POSSIBLY_MODEL", "env-model")
    monkeypatch.setenv("POSSIBLY_REASONING_EFFORT", "low")
    monkeypatch.setenv("POSSIBLY_PROVIDER_CONFIG", '{"temperature":0.2}')
    config = ProviderConfig.resolve(model="explicit-model")
    assert config.model == "explicit-model"
    assert config.entry()["config"]["reasoning_effort"] == "low"
    assert config.entry()["config"]["temperature"] == 0.2
    assert "secret-anthropic" not in json.dumps(config.public())


def test_copilot_all_native_envs_and_precedence(monkeypatch):
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "COPILOT_GITHUB_TOKEN", "COPILOT_AGENT_TOKEN"):
        monkeypatch.setenv(key, key + "-private")
        assert credential_status("github-copilot")["env_var"] == key
        assert ProviderConfig.resolve("github-copilot").entry()["config"]["api_key"] == key + "-private"


def test_settings_are_memory_only_and_do_not_allow_secret_config(monkeypatch):
    monkeypatch.setenv("POSSIBLY_PROVIDER_CONFIG", '{"temperature":0.2}')
    adapter = AmplifierIntelligence(allow_environment=True)
    adapter.configure_provider("openai", "chosen", provider_config={"temperature": 0.5})
    adapter.configure_provider("openai", "chosen-again")
    assert adapter.configuration().options == {"temperature": 0.5}
    assert AmplifierIntelligence().configuration().model is None
    assert "temperature" in adapter.provider_settings()["effective"]["configured_fields"]
    with pytest.raises(PossiblyError):
        checked_config({"nested": {"api_key": "private"}})
    with pytest.raises(PossiblyError):
        ProviderConfig.resolve("not-a-provider")
    monkeypatch.setenv("POSSIBLY_PROVIDER_CONFIG", "not json")
    with pytest.raises(PossiblyError):
        ProviderConfig.resolve()


def test_busy_settings_and_explicit_model_access():
    adapter = AmplifierIntelligence()
    with pytest.raises(PossiblyError, match="--model-env"):
        adapter.test_provider()
    with _ENGINE_LOCK:
        with pytest.raises(PossiblyError, match="active provider"):
            adapter.configure_provider("openai")


def test_test_errors_do_not_return_credentials(monkeypatch):
    async def broken(config):
        raise RuntimeError("secret-key-in-provider-exception")

    monkeypatch.setattr("possibly.providers.prepared_for", broken)
    with pytest.raises(PossiblyError) as exc:
        asyncio.run(connection_test(ProviderConfig("openai"), 1))
    assert "secret-key" not in json.dumps(exc.value.to_dict())


def test_connection_test_calls_provider_once_and_closes_session(monkeypatch):
    calls = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            calls.append("closed")

    async def complete(request):
        calls.append(request)
        return SimpleNamespace(usage={"output_tokens": 1})

    session = Session()
    session.coordinator = SimpleNamespace(
        get=lambda name: {"test": SimpleNamespace(default_model="resolved-model", complete=complete)}
    )

    async def create():
        return session

    async def prepared(config):
        return SimpleNamespace(create_session=create)

    monkeypatch.setattr("possibly.providers.prepared_for", prepared)
    result = asyncio.run(connection_test(ProviderConfig("openai"), 1))
    assert len(calls) == 2 and calls[-1] == "closed"
    assert result["model"] == "resolved-model"
    assert calls[0].max_output_tokens == 64
    assert calls[0].tools is None


def test_provider_login_keeps_tokens_private(monkeypatch):
    async def fake(config, timeout, progress):
        progress("Device code ABCD, visit verification page")
        return {"status": "succeeded", "provider": config.provider}

    monkeypatch.setattr("possibly.providers.login", fake)
    messages = []
    result = AmplifierIntelligence(allow_environment=True).provider_login(
        "openai-chatgpt", on_progress=messages.append
    )
    assert result["status"] == "succeeded"
    assert "ABCD" in messages[0]


def test_oauth_refresh_is_noninteractive(monkeypatch):
    from possibly.providers import refresh_auth

    calls = []

    async def refresh(token, path):
        calls.append((token, path))
        return {"valid": True}

    oauth = SimpleNamespace(
        load_tokens=lambda path: {"refresh_token": "private-refresh"},
        is_token_valid=lambda tokens: bool(tokens and tokens.get("valid")),
        refresh_tokens=refresh,
    )

    async def load(prepared):
        return oauth

    monkeypatch.setattr("possibly.providers.oauth_module", load)
    monkeypatch.setattr(ProviderConfig, "entry", lambda self: {"config": {"token_file_path": "/cache/path"}})
    asyncio.run(refresh_auth(None, ProviderConfig("openai-chatgpt")))
    assert calls == [("private-refresh", "/cache/path")]
    oauth.load_tokens = lambda path: None
    with pytest.raises(PossiblyError, match="missing or expired"):
        asyncio.run(refresh_auth(None, ProviderConfig("openai-chatgpt")))
    assert len(calls) == 1


def test_chatgpt_login_uses_resolver_without_mount_or_returning_tokens(monkeypatch):
    from possibly.providers import login

    class Prepared:
        async def create_session(self):
            raise AssertionError("Do not mount a provider before first login")

    async def prepared(config, require):
        assert not require
        return Prepared()

    async def oauth_login(**kwargs):
        kwargs["print_fn"]("Verification code ABCD")
        return {"access_token": "never-return-this"}

    async def load(prepared):
        return SimpleNamespace(login=oauth_login)

    monkeypatch.setattr("possibly.providers.prepared_for", prepared)
    monkeypatch.setattr("possibly.providers.oauth_module", load)
    messages = []
    result = asyncio.run(login(ProviderConfig("openai-chatgpt"), 1, messages.append))
    assert result["status"] == "succeeded"
    assert "never-return-this" not in json.dumps(result)
    assert messages == ["Verification code ABCD"]


def test_copilot_reuses_gh_cache_without_exposing_token(monkeypatch):
    import os

    from possibly.providers import login

    calls, messages = [], []

    class Process:
        returncode = 0

        async def communicate(self):
            return b"cached-private-token\n", None

    async def command(*args, **kwargs):
        calls.append(args)
        return Process()

    monkeypatch.setattr("possibly.providers.asyncio.create_subprocess_exec", command)
    monkeypatch.setenv("GH_TOKEN", "")
    result = asyncio.run(login(ProviderConfig("github-copilot"), 1, messages.append))
    assert calls == [("gh", "auth", "token", "--hostname", "github.com")]
    assert os.environ["GH_TOKEN"] == "cached-private-token"
    assert "cached-private-token" not in json.dumps(result)
    assert not messages
