from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel, ConfigDict

from codenames_llm.session import (
    ClueDecision,
    ControllerConfigurationError,
    ControllerConfig,
    ControllerExecutionError,
    GuessDecision,
)

logger = logging.getLogger("codenames_llm.openai")


class ClueDecisionModel(BaseModel):
    word: str
    number: int

    model_config = ConfigDict(extra="forbid")


class GuessDecisionModel(BaseModel):
    action: str
    word: str | None = None

    model_config = ConfigDict(extra="forbid")


def create_openai_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as error:
        msg = "The OpenAI SDK is not installed. Add the 'openai' package to use OpenAI controllers."
        raise ControllerConfigurationError(msg) from error

    return OpenAI()


class OpenAIController:
    def decide_clue(
        self,
        *,
        config: ControllerConfig,
        prompt: str,
    ) -> ClueDecision:
        response = self._response_parse(config=config, prompt=prompt, text_format=ClueDecisionModel)
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            msg = "The OpenAI response did not include a parsed clue decision."
            raise ControllerExecutionError(msg)
        return ClueDecision(word=parsed.word, number=parsed.number)

    def decide_guess(
        self,
        *,
        config: ControllerConfig,
        prompt: str,
    ) -> GuessDecision:
        response = self._response_parse(config=config, prompt=prompt, text_format=GuessDecisionModel)
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            msg = "The OpenAI response did not include a parsed guess decision."
            raise ControllerExecutionError(msg)
        action = parsed.action.strip().lower()
        if action not in {"guess", "pass"}:
            msg = f"Unsupported operative action {parsed.action!r}."
            raise ControllerExecutionError(msg)
        return GuessDecision(action=action, word=parsed.word)

    def _response_parse(
        self,
        *,
        config: ControllerConfig,
        prompt: str,
        text_format: type[BaseModel],
    ) -> Any:
        client = create_openai_client()
        responses = getattr(client, "responses", None)
        parse = getattr(responses, "parse", None)
        if parse is None:
            msg = "The installed OpenAI SDK does not support responses.parse."
            raise ControllerConfigurationError(msg)

        request: dict[str, Any] = {
            "model": config.model_name,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You are playing Codenames. Return only a valid structured decision.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            ],
            "text_format": text_format,
        }
        if config.reasoning_effort and config.reasoning_effort != "none":
            request["reasoning"] = {"effort": config.reasoning_effort}

        _log_openai_request(
            model=config.model_name,
            reasoning_effort=config.reasoning_effort.value if config.reasoning_effort else None,
            schema_name=text_format.__name__,
            prompt=prompt,
        )
        try:
            response = parse(**request)
        except Exception as error:  # pragma: no cover - depends on SDK/runtime behavior
            msg = f"OpenAI controller execution failed: {error}"
            raise ControllerExecutionError(msg) from error
        _log_openai_response(
            model=config.model_name,
            schema_name=text_format.__name__,
            parsed=getattr(response, "output_parsed", None),
        )
        return response


def _log_openai_request(
    *,
    model: str,
    reasoning_effort: str | None,
    schema_name: str,
    prompt: str,
) -> None:
    if not _should_log_requests():
        return
    logger.info(
        "OpenAI request: %s",
        json.dumps(
            {
                "model": model,
                "reasoning_effort": reasoning_effort,
                "schema": schema_name,
                "prompt": prompt,
            },
            ensure_ascii=True,
        ),
    )


def _log_openai_response(
    *,
    model: str,
    schema_name: str,
    parsed: Any,
) -> None:
    if not _should_log_requests():
        return
    logger.info(
        "OpenAI parsed response: %s",
        json.dumps(
            {
                "model": model,
                "schema": schema_name,
                "parsed": _serialize_for_logging(parsed),
            },
            ensure_ascii=True,
        ),
    )


def _should_log_requests() -> bool:
    return os.environ.get("CODENAMES_OPENAI_LOG_PROMPTS", "").lower() in {"1", "true", "yes", "on"}


def _serialize_for_logging(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return repr(value)
