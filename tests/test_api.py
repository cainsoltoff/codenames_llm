from __future__ import annotations

from fastapi.testclient import TestClient

from codenames_llm.api import create_app


def test_create_session_returns_expected_view_shape() -> None:
    client = TestClient(create_app())

    response = client.post("/api/sessions", json={"starts": "red", "seed": 7})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["controllers"]["red_spymaster"] == "human"
    assert payload["game"]["active_team"] == "red"
    assert payload["public_board"]["rows"]
    assert payload["spymaster_board"]["rows"]
    assert payload["history"] == []


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
