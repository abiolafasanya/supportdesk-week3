import anthropic
import httpx2
import openai
import pytest

from app.errors import friendly_error


def _response(status):
    return httpx2.Response(status, request=httpx2.Request("POST", "https://api.example.test"))


@pytest.mark.parametrize("sdk", [anthropic, openai])
def test_auth_error_is_not_retryable_and_hides_key(sdk):
    exc = sdk.AuthenticationError("invalid x-api-key sk-secret", response=_response(401), body=None)
    message, retryable = friendly_error(exc)
    assert "API key" in message and "sk-secret" not in message
    assert retryable is False


@pytest.mark.parametrize("sdk", [anthropic, openai])
def test_rate_limit_is_retryable(sdk):
    exc = sdk.RateLimitError("slow down", response=_response(429), body=None)
    assert friendly_error(exc)[1] is True


def test_server_error_is_retryable():
    exc = anthropic.InternalServerError("boom", response=_response(500), body=None)
    assert friendly_error(exc)[1] is True
