"""Lesson 2.4: turn SDK exceptions into clear messages.

Both SDKs use the same class names, so we check both. Order matters:
most specific first, the broad APIStatusError last.
"""
import anthropic
import openai


def _is(exc: Exception, name: str) -> bool:
    return isinstance(exc, (getattr(anthropic, name), getattr(openai, name)))


def friendly_error(exc: Exception) -> tuple[str, bool]:
    """Return (message for the user, should we retry later?). Never includes the key."""
    if _is(exc, "AuthenticationError"):                       # 401
        return "Authentication failed: check the API key in your .env file.", False
    if _is(exc, "PermissionDeniedError"):                     # 403
        return "This key is not allowed to use that model or feature.", False
    if _is(exc, "NotFoundError"):                             # 404
        return "Model not found: check the model name in your .env file.", False
    if _is(exc, "BadRequestError"):                           # 400
        return f"The request was invalid: {getattr(exc, 'message', exc)}", False
    if _is(exc, "RateLimitError"):                            # 429
        return "Rate limit hit, even after retries. Wait a minute and try again.", True
    if _is(exc, "APITimeoutError"):                           # no response in time
        return "The provider took too long to answer. Try again.", True
    if _is(exc, "APIConnectionError"):                        # network problem
        return "Could not reach the provider. Check your internet connection.", True
    if _is(exc, "APIStatusError"):                            # 5xx, 529 overloaded, others
        status = getattr(exc, "status_code", 0)
        return f"The provider returned an error ({status}). Try again shortly.", status >= 500
    raise exc
