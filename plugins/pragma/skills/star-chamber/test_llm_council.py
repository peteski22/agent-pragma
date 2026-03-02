"""Tests for llm_council.py."""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_council import (
    DEFAULT_MAX_TOKENS,
    _get_review_internal,
    _resolve_platform_keys,
    resolve_api_keys,
    run_council,
)


def _mock_acompletion():
    """Create a mock acompletion that returns a valid response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"provider": "test"}'
    return AsyncMock(return_value=mock_response)


class TestMaxTokensPassthrough:
    """Verify max_tokens from provider config is passed to acompletion."""

    def test_default_max_tokens_passed_to_acompletion(self):
        """Default max_tokens should be used when provider config omits it."""
        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        # Use gemini (non-OpenAI) to test the max_tokens path.
        config = {"provider": "gemini", "model": "gemini-2.5-flash", "api_key": "key"}
        with patch.dict(sys.modules, {"any_llm": mock_module}):
            asyncio.run(_get_review_internal(config, "test prompt"))
            assert mock_acompletion.call_args.kwargs.get("max_tokens") == DEFAULT_MAX_TOKENS

    def test_custom_max_tokens_passed_to_acompletion(self):
        """Provider-specified max_tokens should override the default."""
        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        config = {"provider": "anthropic", "model": "claude-opus-4-6", "api_key": "key", "max_tokens": 8192}
        with patch.dict(sys.modules, {"any_llm": mock_module}):
            asyncio.run(_get_review_internal(config, "test prompt"))
            assert mock_acompletion.call_args.kwargs.get("max_tokens") == 8192

    def test_openai_uses_max_completion_tokens(self):
        """OpenAI provider should use max_completion_tokens instead of max_tokens."""
        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        config = {"provider": "openai", "model": "gpt-5.2", "api_key": "key", "max_tokens": 128000}
        with patch.dict(sys.modules, {"any_llm": mock_module}):
            asyncio.run(_get_review_internal(config, "test prompt"))
            call_kwargs = mock_acompletion.call_args.kwargs
            assert call_kwargs.get("max_completion_tokens") == 128000
            assert "max_tokens" not in call_kwargs

    def test_run_council_threads_max_tokens_from_provider(self):
        """run_council should read max_tokens from provider config and pass it through."""
        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        providers = [
            {"provider": "openai", "model": "gpt-5.2", "api_key": "k1", "max_tokens": 128000},
            {"provider": "gemini", "model": "gemini-2.5-flash", "api_key": "k2", "max_tokens": 65536},
            {"provider": "anthropic", "model": "claude-opus-4-6", "api_key": "k3"},
        ]

        with patch.dict(sys.modules, {"any_llm": mock_module}):
            asyncio.run(run_council("test prompt", providers))
            # Index calls by provider to avoid order-dependent assertions.
            calls_by_provider = {
                c.kwargs["provider"]: c.kwargs
                for c in mock_acompletion.call_args_list
            }
            # openai: explicit 128000 via max_completion_tokens.
            assert calls_by_provider["openai"].get("max_completion_tokens") == 128000
            assert "max_tokens" not in calls_by_provider["openai"]
            # gemini: explicit 65536 via max_tokens.
            assert calls_by_provider["gemini"].get("max_tokens") == 65536
            # anthropic: no max_tokens in config, should get default.
            assert calls_by_provider["anthropic"].get("max_tokens") == DEFAULT_MAX_TOKENS


class TestApiBasePassthrough:
    """Verify api_base from provider config is passed to acompletion."""

    def test_api_base_forwarded_to_acompletion(self):
        """api_base should be passed to acompletion when provided."""
        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        config = {"provider": "llamafile", "model": "local-model", "api_key": "", "api_base": "http://gpu-box.local:8080/v1"}
        with patch.dict(sys.modules, {"any_llm": mock_module}):
            asyncio.run(_get_review_internal(config, "test prompt"))
            assert mock_acompletion.call_args.kwargs.get("api_base") == "http://gpu-box.local:8080/v1"

    def test_api_base_omitted_when_empty(self):
        """api_base should not be in kwargs when empty or omitted."""
        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        config = {"provider": "gemini", "model": "gemini-2.5-flash", "api_key": "key"}
        with patch.dict(sys.modules, {"any_llm": mock_module}):
            asyncio.run(_get_review_internal(config, "test prompt"))
            assert "api_base" not in mock_acompletion.call_args.kwargs

    def test_run_council_threads_api_base_from_provider(self):
        """run_council should read api_base from provider config and pass it through."""
        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        providers = [
            {"provider": "llamafile", "model": "local", "api_base": "http://localhost:8080/v1"},
            {"provider": "openai", "model": "gpt-5.2", "api_key": "k1"},
        ]

        with patch.dict(sys.modules, {"any_llm": mock_module}):
            asyncio.run(run_council("test prompt", providers))
            calls_by_provider = {
                c.kwargs["provider"]: c.kwargs
                for c in mock_acompletion.call_args_list
            }
            # llamafile: api_base should be forwarded.
            assert calls_by_provider["llamafile"].get("api_base") == "http://localhost:8080/v1"
            # openai: no api_base in config, should not be in kwargs.
            assert "api_base" not in calls_by_provider["openai"]


def _mock_platform_client_module(mock_client_instance, fetch_error_cls):
    """Create a mock any_llm_platform_client module for patching into sys.modules."""
    mock_module = MagicMock()
    mock_module.AnyLLMPlatformClient = MagicMock(return_value=mock_client_instance)
    mock_module.ProviderKeyFetchError = fetch_error_cls
    return mock_module


# Shared exception class for platform client tests.
_ProviderKeyFetchError = type("ProviderKeyFetchError", (Exception,), {})


class TestResolvePlatformKeys:
    """Verify _resolve_platform_keys() fetches keys and handles local providers."""

    def test_successful_key_fetch(self):
        """Platform keys should be set on providers from fetched results."""
        mock_result = MagicMock()
        mock_result.api_key = "fetched-key-123"

        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(return_value=mock_result)

        providers = [
            {"provider": "openai", "model": "gpt-5.2", "api_key": ""},
        ]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            result = asyncio.run(_resolve_platform_keys(providers, "test-key"))
            assert result[0]["api_key"] == "fetched-key-123"
            mock_client.aget_decrypted_provider_key.assert_awaited_once_with("test-key", "openai")

    def test_uses_production_platform_url_by_default(self):
        """Client should be created with production URL when env var is unset."""
        mock_result = MagicMock()
        mock_result.api_key = "fetched-key"

        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(return_value=mock_result)

        providers = [{"provider": "openai", "model": "gpt-5.2", "api_key": ""}]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ANY_LLM_PLATFORM_URL", None)
                asyncio.run(_resolve_platform_keys(providers, "test-key"))
                mock_mod.AnyLLMPlatformClient.assert_called_once_with(
                    any_llm_platform_url="https://platform-api.any-llm.ai/api/v1",
                )

    def test_respects_platform_url_env_var(self):
        """Client should use ANY_LLM_PLATFORM_URL env var when set."""
        mock_result = MagicMock()
        mock_result.api_key = "fetched-key"

        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(return_value=mock_result)

        providers = [{"provider": "openai", "model": "gpt-5.2", "api_key": ""}]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            with patch.dict(os.environ, {"ANY_LLM_PLATFORM_URL": "http://localhost:8000"}):
                asyncio.run(_resolve_platform_keys(providers, "test-key"))
                mock_mod.AnyLLMPlatformClient.assert_called_once_with(
                    any_llm_platform_url="http://localhost:8000/api/v1",
                )

    def test_respects_platform_url_env_var_trailing_slash(self):
        """Client should normalize ANY_LLM_PLATFORM_URL when it has a trailing slash."""
        mock_result = MagicMock()
        mock_result.api_key = "fetched-key"

        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(return_value=mock_result)

        providers = [{"provider": "openai", "model": "gpt-5.2", "api_key": ""}]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            with patch.dict(os.environ, {"ANY_LLM_PLATFORM_URL": "http://localhost:8000/"}):
                asyncio.run(_resolve_platform_keys(providers, "test-key"))
                mock_mod.AnyLLMPlatformClient.assert_called_once_with(
                    any_llm_platform_url="http://localhost:8000/api/v1",
                )

    def test_does_not_double_append_api_v1(self):
        """Client should not append /api/v1 when URL already contains it."""
        mock_result = MagicMock()
        mock_result.api_key = "fetched-key"

        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(return_value=mock_result)

        providers = [{"provider": "openai", "model": "gpt-5.2", "api_key": ""}]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            with patch.dict(os.environ, {"ANY_LLM_PLATFORM_URL": "http://localhost:8000/api/v1"}):
                asyncio.run(_resolve_platform_keys(providers, "test-key"))
                mock_mod.AnyLLMPlatformClient.assert_called_once_with(
                    any_llm_platform_url="http://localhost:8000/api/v1",
                )

    def test_returns_new_dicts(self):
        """Returned provider dicts should not be the same objects as the input."""
        mock_result = MagicMock()
        mock_result.api_key = "fetched-key"

        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(return_value=mock_result)

        original = {"provider": "openai", "model": "gpt-5.2", "api_key": ""}
        providers = [original]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            result = asyncio.run(_resolve_platform_keys(providers, "test-key"))
            assert result[0] is not original
            assert original["api_key"] == ""  # original unchanged

    def test_local_provider_tolerates_fetch_error(self):
        """Local providers should get empty api_key when platform fetch fails."""
        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(
            side_effect=_ProviderKeyFetchError("no key"),
        )

        providers = [
            {"provider": "llamafile", "model": "local-model", "api_key": "", "local": True},
        ]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            result = asyncio.run(_resolve_platform_keys(providers, "test-key"))
            assert result[0]["api_key"] == ""

    def test_local_provider_tolerates_network_error(self):
        """Local providers should survive non-ProviderKeyFetchError exceptions."""
        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(
            side_effect=ConnectionError("platform unreachable"),
        )

        providers = [
            {"provider": "llamafile", "model": "local-model", "api_key": "", "local": True},
        ]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            result = asyncio.run(_resolve_platform_keys(providers, "test-key"))
            assert result[0]["api_key"] == ""

    def test_non_local_provider_raises_on_fetch_error(self):
        """Non-local providers should re-raise ProviderKeyFetchError."""
        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(
            side_effect=_ProviderKeyFetchError("no key"),
        )

        providers = [
            {"provider": "openai", "model": "gpt-5.2", "api_key": ""},
        ]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            with pytest.raises(_ProviderKeyFetchError):
                asyncio.run(_resolve_platform_keys(providers, "test-key"))

    def test_non_local_provider_raises_on_network_error(self):
        """Non-local providers should re-raise network errors."""
        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(
            side_effect=ConnectionError("platform unreachable"),
        )

        providers = [
            {"provider": "openai", "model": "gpt-5.2", "api_key": ""},
        ]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            with pytest.raises(ConnectionError):
                asyncio.run(_resolve_platform_keys(providers, "test-key"))

    def test_local_provider_uses_platform_key_when_available(self):
        """Local providers should use the platform key when fetching succeeds."""
        mock_result = MagicMock()
        mock_result.api_key = "platform-key-for-local"

        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(return_value=mock_result)

        providers = [
            {"provider": "llamafile", "model": "local-model", "api_key": "", "local": True},
        ]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            result = asyncio.run(_resolve_platform_keys(providers, "test-key"))
            assert result[0]["api_key"] == "platform-key-for-local"


class TestResolveApiKeys:
    """Verify resolve_api_keys() handles both modes correctly."""

    def test_direct_mode_expands_env_vars(self):
        """Direct mode should expand ${ENV_VAR} references."""
        providers = [
            {"provider": "openai", "model": "gpt-5.2", "api_key": "${OPENAI_API_KEY}"},
        ]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            result = asyncio.run(resolve_api_keys(providers, use_platform=False))
            assert result[0]["api_key"] == "sk-test"

    def test_direct_mode_returns_new_dicts(self):
        """Direct mode should return new dicts, not mutate originals."""
        original = {"provider": "openai", "model": "gpt-5.2", "api_key": "${OPENAI_API_KEY}"}
        providers = [original]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            result = asyncio.run(resolve_api_keys(providers, use_platform=False))
            assert result[0] is not original
            assert original["api_key"] == "${OPENAI_API_KEY}"  # unchanged

    def test_direct_mode_preserves_local_field(self):
        """The local field should pass through env var expansion unchanged."""
        providers = [
            {"provider": "llamafile", "model": "local", "api_key": "", "local": True},
            {"provider": "openai", "model": "gpt-5.2", "api_key": "${OPENAI_API_KEY}"},
        ]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            result = asyncio.run(resolve_api_keys(providers, use_platform=False))
            assert result[0]["local"] is True
            assert result[1]["api_key"] == "sk-test"
            assert result[0]["api_key"] == ""

    def test_platform_mode_delegates_to_resolve_platform_keys(self):
        """Platform mode should call _resolve_platform_keys."""
        mock_result = MagicMock()
        mock_result.api_key = "platform-key"

        mock_client = MagicMock()
        mock_client.aget_decrypted_provider_key = AsyncMock(return_value=mock_result)

        providers = [
            {"provider": "openai", "model": "gpt-5.2"},
        ]

        mock_mod = _mock_platform_client_module(mock_client, _ProviderKeyFetchError)
        with patch.dict(sys.modules, {"any_llm_platform_client": mock_mod}):
            result = asyncio.run(resolve_api_keys(providers, use_platform=True, any_llm_key="test-key"))
            assert result[0]["api_key"] == "platform-key"


class TestLocalProviderErrorMessage:
    """Verify local providers get better auth error messages."""

    def test_local_provider_auth_error_message(self):
        """Local provider auth errors should suggest platform or providers.json."""
        mock_acompletion = AsyncMock(side_effect=Exception("401 Unauthorized"))
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        config = {"provider": "llamafile", "model": "local-model", "api_key": "", "local": True}
        with patch.dict(sys.modules, {"any_llm": mock_module}):
            result = asyncio.run(_get_review_internal(config, "test"))
            assert not result["success"]
            assert "Local provider llamafile" in result["error"]
            assert "providers.json" in result["error"]

    def test_non_local_provider_auth_error_unchanged(self):
        """Non-local provider auth errors should keep the standard message."""
        mock_acompletion = AsyncMock(side_effect=Exception("401 Unauthorized"))
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        config = {"provider": "openai", "model": "gpt-5.2", "api_key": ""}
        with patch.dict(sys.modules, {"any_llm": mock_module}):
            result = asyncio.run(_get_review_internal(config, "test"))
            assert not result["success"]
            assert "Authentication failed for openai" in result["error"]

    def test_auth_detection_covers_all_patterns(self):
        """Auth detection should catch 'api key' (with space) and 'apikey' for all providers."""
        mock_module = MagicMock()

        for error_text in ["missing api key", "invalid apikey", "api_key required", "401 error", "Unauthorized"]:
            mock_module.acompletion = AsyncMock(side_effect=Exception(error_text))
            config = {"provider": "openai", "model": "gpt-5.2", "api_key": ""}
            with patch.dict(sys.modules, {"any_llm": mock_module}):
                result = asyncio.run(_get_review_internal(config, "test"))
                assert "Authentication failed" in result["error"], f"Failed to detect auth error: {error_text}"


class TestInputFile:
    """Verify --input-file reads prompt from a file instead of stdin."""

    def _make_config(self, tmp_path):
        """Create a minimal providers.json for main() to load."""
        config = {
            "providers": [
                {"provider": "openai", "model": "gpt-5.2", "api_key": "sk-test"},
            ],
        }
        config_file = tmp_path / "providers.json"
        config_file.write_text(json.dumps(config))
        return config_file

    def test_input_file_reads_from_file(self, tmp_path):
        """Prompt should be read from --input-file when provided."""
        import io

        from llm_council import main

        config_file = self._make_config(tmp_path)
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Review this code please")

        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        with (
            patch("sys.argv", ["llm_council.py", "--input-file", str(prompt_file)]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_stdout,
            patch.dict(os.environ, {"STAR_CHAMBER_CONFIG": str(config_file)}, clear=False),
            patch.dict(sys.modules, {"any_llm": mock_module}),
        ):
            main()

        output = json.loads(mock_stdout.getvalue())
        assert output["reviews"]
        # Verify the prompt reached acompletion (first positional or messages kwarg).
        call_kwargs = mock_acompletion.call_args.kwargs
        messages = call_kwargs["messages"]
        assert "Review this code please" in messages[0]["content"]

    def test_input_file_missing_exits_with_error(self, tmp_path):
        """Non-existent --input-file should produce error JSON and exit 1."""
        import io

        from llm_council import main

        config_file = self._make_config(tmp_path)

        with (
            patch("sys.argv", ["llm_council.py", "--input-file", "/nonexistent/prompt.txt"]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_stdout,
            patch.dict(os.environ, {"STAR_CHAMBER_CONFIG": str(config_file)}, clear=False),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        output = json.loads(mock_stdout.getvalue())
        assert "Input file not found" in output["error"]

    def test_input_file_directory_exits_with_error(self, tmp_path):
        """Directory path should produce error JSON and exit 1, not a traceback."""
        import io

        from llm_council import main

        config_file = self._make_config(tmp_path)

        with (
            patch("sys.argv", ["llm_council.py", "--input-file", str(tmp_path)]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_stdout,
            patch.dict(os.environ, {"STAR_CHAMBER_CONFIG": str(config_file)}, clear=False),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        output = json.loads(mock_stdout.getvalue())
        assert "Failed to read input file" in output["error"]

    def test_stdin_still_works_without_input_file(self, tmp_path):
        """Stdin should be used when --input-file is omitted (backwards compat)."""
        import io

        from llm_council import main

        config_file = self._make_config(tmp_path)

        mock_acompletion = _mock_acompletion()
        mock_module = MagicMock()
        mock_module.acompletion = mock_acompletion

        with (
            patch("sys.argv", ["llm_council.py"]),
            patch("sys.stdin", io.StringIO("Prompt from stdin")),
            patch("sys.stdout", new_callable=io.StringIO) as mock_stdout,
            patch.dict(os.environ, {"STAR_CHAMBER_CONFIG": str(config_file)}, clear=False),
            patch.dict(sys.modules, {"any_llm": mock_module}),
        ):
            main()

        output = json.loads(mock_stdout.getvalue())
        assert output["reviews"]
        call_kwargs = mock_acompletion.call_args.kwargs
        messages = call_kwargs["messages"]
        assert "Prompt from stdin" in messages[0]["content"]


class TestListSdksLocalProviders:
    """Verify --list-sdks output categorizes local providers correctly."""

    def test_local_providers_not_in_missing_key(self, tmp_path):
        """Local providers should appear in providers_local, not providers_missing_key."""
        from llm_council import main
        import io

        config = {
            "providers": [
                {"provider": "openai", "model": "gpt-5.2", "api_key": "${OPENAI_API_KEY}"},
                {"provider": "llamafile", "model": "local", "api_base": "http://localhost:8080/v1", "local": True},
            ],
        }
        config_file = tmp_path / "providers.json"
        config_file.write_text(json.dumps(config))

        with (
            patch("llm_council.load_sdk_map", return_value={"anthropic": "anthropic"}),
            patch("sys.argv", ["llm_council.py", "--list-sdks"]),
            pytest.raises(SystemExit) as exc_info,
            patch("sys.stdout", new_callable=io.StringIO) as mock_stdout,
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "STAR_CHAMBER_CONFIG": str(config_file)}, clear=False),
        ):
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert "llamafile" in output["providers_local"]
        assert "llamafile" not in output["providers_missing_key"]
        assert "openai" in output["providers_missing_key"]
