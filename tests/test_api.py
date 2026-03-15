from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from codenames_llm.api import create_app


class _FakeResponse:
    def __init__(self, output_parsed) -> None:
        self.output_parsed = output_parsed


class _FakeResponses:
    def __init__(self, outputs) -> None:
        self._outputs = iter(outputs)

    def parse(self, **_: object) -> _FakeResponse:
        return _FakeResponse(next(self._outputs))


class _FakeClient:
    def __init__(self, outputs) -> None:
        self.responses = _FakeResponses(outputs)


class _ClueDecision:
    def __init__(self, word: str, number: int) -> None:
        self.word = word
        self.number = number


class _GuessDecision:
    def __init__(self, action: str, word: str | None = None) -> None:
        self.action = action
        self.word = word


def test_create_session_returns_expected_view_shape() -> None:
    client = TestClient(create_app())

    response = client.post("/api/sessions", json={"starts": "red", "seed": 7})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["controllers"]["red_spymaster"]["kind"] == "human"
    assert payload["controllers"]["red_spymaster"]["prompt_preset"] is None
    assert payload["active_controller"]["kind"] == "human"
    assert payload["game"]["active_team"] == "red"
    assert payload["public_board"]["rows"]
    assert payload["spymaster_board"]["rows"]
    assert payload["history"] == []
    assert payload["ai_trace"] == []


def test_get_session_returns_existing_state() -> None:
    client = TestClient(create_app())
    created = client.post("/api/sessions", json={"starts": "red"}).json()

    response = client.get(f"/api/sessions/{created['session_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == created["session_id"]
    assert payload["game"]["phase"] == "clue"


def test_clue_guess_and_pass_flow_updates_state() -> None:
    client = TestClient(create_app())
    created = client.post("/api/sessions", json={"starts": "red"}).json()
    session_id = created["session_id"]
    red_word = next(
        card["word"]
        for card in created["spymaster_board"]["cards"]
        if card["role"] == "red_agent"
    )

    clue_response = client.post(
        f"/api/sessions/{session_id}/clue",
        json={"word": "ocean", "number": 1},
    )
    assert clue_response.status_code == 200
    clue_payload = clue_response.json()
    assert clue_payload["game"]["phase"] == "guess"
    assert clue_payload["game"]["guesses_remaining"] == 2

    guess_response = client.post(
        f"/api/sessions/{session_id}/guess",
        json={"word": red_word},
    )
    assert guess_response.status_code == 200
    guess_payload = guess_response.json()
    assert guess_payload["history"][-1]["type"] == "guess"

    pass_response = client.post(f"/api/sessions/{session_id}/pass", json={})
    assert pass_response.status_code == 200
    pass_payload = pass_response.json()
    assert pass_payload["game"]["phase"] == "clue"


def test_step_endpoint_advances_ai_spymaster(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(create_app())
    monkeypatch.setattr(
        "codenames_llm.controllers.openai_controller.create_openai_client",
        lambda: _FakeClient([_ClueDecision("ocean", 1)]),
    )

    created = client.post(
        "/api/sessions",
        json={
            "starts": "red",
            "controllers": {
                "red_spymaster": {
                    "kind": "openai",
                    "model": "gpt-5.4",
                    "reasoning_effort": "low",
                    "prompt_preset": "aggressive_cluegiver",
                }
            },
        },
    ).json()

    response = client.post(f"/api/sessions/{created['session_id']}/step", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["game"]["phase"] == "guess"
    assert payload["game"]["current_clue"] == {"word": "ocean", "number": 1}
    assert payload["ai_trace"][-1]["status"] == "succeeded"
    assert payload["controllers"]["red_spymaster"]["prompt_preset"] == "aggressive_cluegiver"
    assert "Prompt preset: aggressive_cluegiver" in payload["ai_trace"][-1]["prompt"]


def test_run_endpoint_stops_on_next_human_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(create_app())
    fake_client = _FakeClient([
        _ClueDecision("ocean", 1),
        _GuessDecision("pass"),
    ])
    monkeypatch.setattr(
        "codenames_llm.controllers.openai_controller.create_openai_client",
        lambda: fake_client,
    )

    created = client.post(
        "/api/sessions",
        json={
            "starts": "red",
            "controllers": {
                "red_spymaster": {"kind": "openai", "model": "gpt-5.4"},
                "red_operative": {"kind": "openai", "model": "gpt-5.4"},
            },
        },
    ).json()

    response = client.post(
        f"/api/sessions/{created['session_id']}/run",
        json={"max_steps": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game"]["active_player"] == "blue_spymaster"
    assert payload["awaiting_human_input"] is True
    assert len(payload["ai_trace"]) == 2


def test_turn_endpoint_advances_one_complete_ai_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(create_app())
    fake_client = _FakeClient([
        _ClueDecision("ocean", 1),
        _GuessDecision("pass"),
    ])
    monkeypatch.setattr(
        "codenames_llm.controllers.openai_controller.create_openai_client",
        lambda: fake_client,
    )

    created = client.post(
        "/api/sessions",
        json={
            "starts": "red",
            "controllers": {
                "red_spymaster": {"kind": "openai", "model": "gpt-5.4"},
                "red_operative": {"kind": "openai", "model": "gpt-5.4"},
            },
        },
    ).json()

    response = client.post(
        f"/api/sessions/{created['session_id']}/turn",
        json={"max_steps": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game"]["turn_number"] == 2
    assert payload["game"]["active_player"] == "blue_spymaster"
    assert len(payload["ai_trace"]) == 2


def test_step_endpoint_rejects_human_turn() -> None:
    client = TestClient(create_app())
    created = client.post("/api/sessions", json={"starts": "red"}).json()

    response = client.post(f"/api/sessions/{created['session_id']}/step", json={})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "human_input_required"


def test_invalid_actions_return_structured_400() -> None:
    client = TestClient(create_app())
    created = client.post("/api/sessions", json={"starts": "red"}).json()
    session_id = created["session_id"]

    response = client.post(
        f"/api/sessions/{session_id}/guess",
        json={"word": created["public_board"]["cards"][0]["word"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_action"


def test_public_view_hides_unrevealed_roles() -> None:
    client = TestClient(create_app())
    created = client.post("/api/sessions", json={"starts": "red"}).json()

    public_card = created["public_board"]["cards"][0]
    spymaster_card = created["spymaster_board"]["cards"][0]

    assert public_card["role"] is None
    assert public_card["color"] == "neutral"
    assert spymaster_card["role"] is not None


def test_missing_session_returns_404() -> None:
    client = TestClient(create_app())

    response = client.get("/api/sessions/missing")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "session_not_found"
