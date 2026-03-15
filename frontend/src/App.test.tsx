import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import App from "./App";

const sampleSession = {
  session_id: "session-1",
  seed: 7,
  controllers: {
    red_spymaster: {
      kind: "openai",
      model: "gpt-5.4",
      reasoning_effort: "low",
      prompt_preset: "aggressive_cluegiver",
    },
    red_operative: { kind: "human", model: null, reasoning_effort: null, prompt_preset: null },
    blue_spymaster: { kind: "human", model: null, reasoning_effort: null, prompt_preset: null },
    blue_operative: { kind: "human", model: null, reasoning_effort: null, prompt_preset: null },
  },
  active_controller: {
    kind: "openai",
    model: "gpt-5.4",
    reasoning_effort: "low",
    prompt_preset: "aggressive_cluegiver",
  },
  awaiting_human_input: false,
  can_step: true,
  game: {
    status: "ongoing",
    phase: "guess",
    round_number: 2,
    turn_number: 3,
    active_team: "red",
    active_player: "red_operative",
    current_clue: { word: "ocean", number: 2 },
    guesses_remaining: 3,
    winner: null,
    remaining_agents: { red: 9, blue: 8 },
  },
  public_board: {
    cards: [
      { index: 0, word: "alpha", revealed: false, role: null, color: "neutral" },
    ],
    rows: [[{ index: 0, word: "alpha", revealed: false, role: null, color: "neutral" }]],
  },
  spymaster_board: {
    cards: [
      { index: 0, word: "alpha", revealed: false, role: "red_agent", color: "red" },
    ],
    rows: [[{ index: 0, word: "alpha", revealed: false, role: "red_agent", color: "red" }]],
  },
  history: [
    {
      type: "clue",
      team: "red",
      player: "red_spymaster",
      round_number: 1,
      turn_number: 1,
      clue: { word: "animal", number: 1 },
    },
    {
      type: "pass",
      team: "blue",
      player: "blue_operative",
      round_number: 1,
      turn_number: 2,
    },
    {
      type: "clue",
      team: "red",
      player: "red_spymaster",
      round_number: 2,
      turn_number: 3,
      clue: { word: "ocean", number: 2 },
    },
    {
      type: "guess",
      team: "red",
      player: "red_operative",
      round_number: 2,
      turn_number: 3,
      guessed_word: "alpha",
      revealed_role: "red_agent",
      was_correct: true,
      ended_turn: false,
      ended_game: false,
    },
  ],
  ai_trace: [],
};

describe("App", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/sessions") && init?.method === "POST") {
        return {
          ok: true,
          json: async () => sampleSession,
        } as Response;
      }
      if (url.endsWith("/step")) {
        return {
          ok: true,
          json: async () => ({
            ...sampleSession,
            ai_trace: [
              {
                sequence: 1,
                role: "red_spymaster",
                team: "red",
                controller: {
                  kind: "openai",
                  model: "gpt-5.4",
                  reasoning_effort: "low",
                  prompt_preset: "aggressive_cluegiver",
                },
                action_type: "clue",
                prompt: "You are the active spymaster in a game of Codenames.",
                decision: { word: "ocean", number: 1 },
                status: "succeeded",
                message: "red_spymaster gave clue ocean 1.",
                attempts: 1,
              },
            ],
          }),
        } as Response;
      }
      if (url.endsWith("/turn")) {
        return {
          ok: true,
          json: async () => ({
            ...sampleSession,
            game: {
              ...sampleSession.game,
              turn_number: 4,
              active_team: "blue",
              active_player: "blue_spymaster",
              guesses_remaining: null,
              current_clue: null,
              phase: "clue",
            },
          }),
        } as Response;
      }
      return {
        ok: true,
        json: async () => sampleSession,
      } as Response;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a session and exposes AI controls for an openai turn", async () => {
    render(<App />);

    await userEvent.selectOptions(screen.getAllByLabelText("Controller")[0], "openai");
    await userEvent.selectOptions(screen.getByLabelText("Prompt style"), "aggressive_cluegiver");
    await userEvent.click(screen.getByRole("button", { name: "Create session" }));

    await waitFor(() => {
      expect(screen.getByText("Session: session-1")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Red Spymaster").length).toBeGreaterThan(0);
    expect(screen.getAllByText("GPT").length).toBeGreaterThan(0);
    expect(screen.getByText("Current Clue")).toBeInTheDocument();
    expect(screen.getByText("Guesses Remaining")).toBeInTheDocument();
    expect(screen.getByText("Current Turn Guesses")).toBeInTheDocument();
    expect(screen.getAllByText("alpha").length).toBeGreaterThan(0);
    expect(screen.getByText("Round 2")).toBeInTheDocument();
    expect(screen.getByText("Latest")).toBeInTheDocument();
    expect(screen.getByText("Public Board")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Step AI Turn" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Advance Turn" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Step AI Turn" }));
    await waitFor(() => {
      expect(screen.getByText("Prompt Debug")).toBeInTheDocument();
    });
    expect(screen.getByText("You are the active spymaster in a game of Codenames.")).toBeInTheDocument();
  });
});
