import type { ControllerConfig, SessionView } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: { message?: string } };
      message = payload.detail?.message ?? message;
    } catch {
      // Leave generic fallback in place.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export function createSession(
  starts: "red" | "blue",
  seed: number | null,
  controllers: Record<string, ControllerConfig>,
): Promise<SessionView> {
  return requestJson<SessionView>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      starts,
      seed,
      controllers,
    }),
  });
}

export function getSession(sessionId: string): Promise<SessionView> {
  return requestJson<SessionView>(`/api/sessions/${sessionId}`);
}

export function submitClue(
  sessionId: string,
  word: string,
  number: number,
): Promise<SessionView> {
  return requestJson<SessionView>(`/api/sessions/${sessionId}/clue`, {
    method: "POST",
    body: JSON.stringify({ word, number }),
  });
}

export function submitGuess(sessionId: string, word: string): Promise<SessionView> {
  return requestJson<SessionView>(`/api/sessions/${sessionId}/guess`, {
    method: "POST",
    body: JSON.stringify({ word }),
  });
}

export function submitPass(sessionId: string): Promise<SessionView> {
  return requestJson<SessionView>(`/api/sessions/${sessionId}/pass`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function stepAiTurn(sessionId: string): Promise<SessionView> {
  return requestJson<SessionView>(`/api/sessions/${sessionId}/step`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function runAiTurns(sessionId: string, maxSteps = 20): Promise<SessionView> {
  return requestJson<SessionView>(`/api/sessions/${sessionId}/run`, {
    method: "POST",
    body: JSON.stringify({ max_steps: maxSteps }),
  });
}

export function advanceAiTurn(sessionId: string, maxSteps = 20): Promise<SessionView> {
  return requestJson<SessionView>(`/api/sessions/${sessionId}/turn`, {
    method: "POST",
    body: JSON.stringify({ max_steps: maxSteps }),
  });
}
