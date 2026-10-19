"""The single gateway to every model (CLAUDE.md §2, §4).

One client, one key. No provider-native API is called and no provider-native
key exists, so adding a model is a registry entry and a routing line rather than
a new client and a new secret.

The key is read from settings where the client is built and goes nowhere else:
never into graph state, a prompt, a tool result, or a log record (§8).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Final

import openai
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.observability import usage

logger = logging.getLogger("app")

OPENROUTER_BASE_URL: Final = "https://openrouter.ai/api/v1"

# A hung provider must not hold a turn open indefinitely, so the budget is
# explicit rather than left to the SDK's default.
REQUEST_TIMEOUT_SECONDS: Final = 30.0
MAX_RETRIES: Final = 2

# OpenRouter's provider routing. `require_parameters` is documented as "only
# use providers that support all parameters in your request"; without it,
# parameters are only a soft preference when OpenRouter chooses between the
# providers serving a model, so a request carrying tools could be routed to one
# that ignores them — a reply that silently skips tool use is indistinguishable
# from a broken agent.
#
# It travels in `extra_body`, which is what `langchain-openai` exposes for body
# passthrough. `tests/test_openrouter_client.py` asserts it on the wire rather
# than trusting this comment — picking the wrong field drops the constraint
# silently instead of raising.
PROVIDER_ROUTING: Final[dict[str, Any]] = {"require_parameters": True}


class GatewayError(RuntimeError):
    """A model call could not be completed.

    Carries a stable error class and a reason safe to show a caller. The
    provider's own response body is deliberately not included: it can echo
    request headers, and nothing downstream needs it.
    """

    def __init__(self, error_class: str, reason: str) -> None:
        super().__init__(reason)
        self.error_class = error_class
        self.reason = reason


@dataclass(frozen=True, slots=True)
class _Mapping:
    error_class: str
    reason: str


# Ordered most specific first: APITimeoutError subclasses APIConnectionError,
# and both subclass APIError.
_MAPPINGS: Final[tuple[tuple[type[Exception], _Mapping], ...]] = (
    (
        openai.APITimeoutError,
        _Mapping("timeout", "the model did not respond within its time budget"),
    ),
    (
        openai.APIConnectionError,
        _Mapping("unreachable", "the model gateway could not be reached"),
    ),
    (
        openai.RateLimitError,
        _Mapping("rate_limited", "the model gateway rate-limited this request"),
    ),
    (
        openai.AuthenticationError,
        _Mapping("unauthorized", "the model gateway rejected our credentials"),
    ),
    (
        openai.PermissionDeniedError,
        _Mapping("forbidden", "the model gateway refused this request"),
    ),
)


def _classify(error: Exception) -> _Mapping:
    for kind, mapping in _MAPPINGS:
        if isinstance(error, kind):
            return mapping
    if isinstance(error, openai.APIStatusError):
        # Covers the case where `require_parameters` leaves no eligible
        # provider: OpenRouter answers with a status rather than a reply.
        return _Mapping(
            "refused",
            f"the model gateway refused this request (HTTP {error.status_code})",
        )
    return _Mapping("gateway_error", "the model gateway returned an error")


@contextmanager
def gateway_errors(*, operation: str) -> Iterator[None]:
    """Turn any gateway failure into a `GatewayError` and one log record.

    The raw exception never escapes: its string form can carry a provider
    payload, and `str(error)` is precisely what must not reach a caller.

    Every model call in this codebase runs inside this context manager, so it
    is also where `app.observability.usage.UsageRecorder` learns which operation
    a call belongs to.
    """
    with usage.operation(operation):
        try:
            yield
        except openai.OpenAIError as error:
            mapping = _classify(error)
            logger.warning(
                "model call failed",
                extra={
                    "context": {
                        "operation": operation,
                        "error_class": mapping.error_class,
                        "error_type": type(error).__name__,
                    }
                },
            )
            raise GatewayError(mapping.error_class, mapping.reason) from error


def build_chat_model(
    settings: Settings,
    *,
    model_id: str,
    http_client: Any | None = None,
    **kwargs: Any,
) -> ChatOpenAI:
    """A model, pointed at OpenRouter.

    `model_id` is always explicit: the application routes per agent slot
    (CLAUDE.md §4), so there is no single default model. `api_key` is always
    passed explicitly so the client can never fall back to an ambient
    `OPENAI_API_KEY`, which would mean calling a different gateway than the one
    this application is configured for.

    No temperature or output cap is set by default. Several registry models
    accept only their default temperature; a per-model generation profile passes
    `temperature` and `max_tokens` through `kwargs` only where the registry says
    the model supports them.
    """
    extra: dict[str, Any] = {"provider": PROVIDER_ROUTING}
    extra.update(kwargs.pop("extra_body", None) or {})

    options: dict[str, Any] = {
        "model": model_id,
        "base_url": OPENROUTER_BASE_URL,
        "api_key": settings.openrouter_api_key.get_secret_value(),
        "timeout": REQUEST_TIMEOUT_SECONDS,
        "max_retries": MAX_RETRIES,
        "extra_body": extra,
    }
    if http_client is not None:
        options["http_client"] = http_client
    options.update(kwargs)
    return ChatOpenAI(**options)
