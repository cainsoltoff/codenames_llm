import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import App from "./App";

const sampleSession = {
  session_id: "session-1",
  seed: 7,
  controllers: {
    red_spymaster: "human",
    red_operative: "human",
    blue_spymaster: "human",
    blue_operative: "human",
  },
  game: {
    status: "ongoing",
    phase: "clue",
    round_number: 1,
    turn_number: 1,
    active_team: "red",
    active_player: "red_spymaster",
    current_clue: null,
    guesses_remaining: null,
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
  history: [],
};

describe("App", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => sampleSession,
    } as Response);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a session and renders the board", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Create session" }));

    await waitFor(() => {
      expect(screen.getByText("Session: session-1")).toBeInTheDocument();
    });
    expect(screen.getByText("Public Board")).toBeInTheDocument();
    expect(screen.getAllByText("alpha")).toHaveLength(2);
  });
});
