export type ControllerKind = "human";

export type SessionView = {
  session_id: string;
  seed: number | null;
  controllers: Record<string, ControllerKind>;
  game: {
    status: "ongoing" | "game_over";
    phase: "clue" | "guess";
    round_number: number;
    turn_number: number;
    active_team: "red" | "blue";
    active_player: string;
    current_clue: { word: string; number: number } | null;
    guesses_remaining: number | null;
    winner: "red" | "blue" | null;
    remaining_agents: {
      red: number;
      blue: number;
    };
  };
  public_board: BoardView;
  spymaster_board: BoardView;
  history: HistoryEventView[];
};

export type BoardView = {
  cards: CardView[];
  rows: CardView[][];
};

export type CardView = {
  index: number;
  word: string;
  revealed: boolean;
  role: string | null;
  color: "neutral" | "red" | "blue" | "white" | "black";
};

export type HistoryEventView = {
  type: "clue" | "guess" | "pass";
  team: "red" | "blue";
  player: string;
  round_number: number;
  turn_number: number;
  clue?: { word: string; number: number };
  guessed_word?: string;
  revealed_role?: string;
  was_correct?: boolean;
  ended_turn?: boolean;
  ended_game?: boolean;
};
