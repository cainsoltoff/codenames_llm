import { useEffect, useState } from "react";
import {
  createSession,
  getSession,
  runAiTurns,
  stepAiTurn,
  submitClue,
  submitGuess,
  submitPass,
} from "./api";
import type {
  AITraceEntry,
  CardView,
  ControllerConfig,
  ControllerKind,
  HistoryEventView,
  ReasoningEffort,
  SessionView,
} from "./types";

const POLL_INTERVAL_MS = 2500;
const ROLE_KEYS = [
  "red_spymaster",
  "red_operative",
  "blue_spymaster",
  "blue_operative",
] as const;

const CARD_CLASS_BY_COLOR: Record<CardView["color"], string> = {
  neutral: "card--neutral",
  red: "card--red",
  blue: "card--blue",
  white: "card--white",
  black: "card--black",
};

const DEFAULT_HUMAN_CONFIG: ControllerConfig = {
  kind: "human",
  model: null,
  reasoning_effort: null,
};

const DEFAULT_OPENAI_CONFIG: ControllerConfig = {
  kind: "openai",
  model: "gpt-5.4",
  reasoning_effort: "low",
};

const DEFAULT_CONTROLLERS: Record<string, ControllerConfig> = {
  red_spymaster: { ...DEFAULT_HUMAN_CONFIG },
  red_operative: { ...DEFAULT_HUMAN_CONFIG },
  blue_spymaster: { ...DEFAULT_HUMAN_CONFIG },
  blue_operative: { ...DEFAULT_HUMAN_CONFIG },
};

export default function App() {
  const [session, setSession] = useState<SessionView | null>(null);
  const [starts, setStarts] = useState<"red" | "blue">("red");
  const [seed, setSeed] = useState("");
  const [controllers, setControllers] =
    useState<Record<string, ControllerConfig>>(DEFAULT_CONTROLLERS);
  const [clueWord, setClueWord] = useState("");
  const [clueNumber, setClueNumber] = useState("1");
  const [guessWord, setGuessWord] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isAdvancingAi, setIsAdvancingAi] = useState(false);

  useEffect(() => {
    if (!session) {
      return undefined;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const latest = await getSession(session.session_id);
        setSession(latest);
        setError(null);
      } catch (pollError) {
        const message = (pollError as Error).message;
        setError(message);
        if (message.includes("was not found")) {
          setSession(null);
        }
      }
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [session?.session_id]);

  async function handleCreateSession(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const nextSession = await createSession(
        starts,
        seed === "" ? null : Number(seed),
        controllers,
      );
      setSession(nextSession);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleClueSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) {
      return;
    }
    setError(null);
    try {
      const nextSession = await submitClue(session.session_id, clueWord, Number(clueNumber));
      setSession(nextSession);
      setClueWord("");
      setClueNumber("1");
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }

  async function handleGuessSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) {
      return;
    }
    setError(null);
    try {
      const nextSession = await submitGuess(session.session_id, guessWord);
      setSession(nextSession);
      setGuessWord("");
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }

  async function handlePass() {
    if (!session) {
      return;
    }
    setError(null);
    try {
      const nextSession = await submitPass(session.session_id);
      setSession(nextSession);
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }

  async function handleAiStep() {
    if (!session) {
      return;
    }
    setIsAdvancingAi(true);
    setError(null);
    try {
      const nextSession = await stepAiTurn(session.session_id);
      setSession(nextSession);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setIsAdvancingAi(false);
    }
  }

  async function handleAiRun() {
    if (!session) {
      return;
    }
    setIsAdvancingAi(true);
    setError(null);
    try {
      const nextSession = await runAiTurns(session.session_id);
      setSession(nextSession);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setIsAdvancingAi(false);
    }
  }

  function updateControllerKind(role: string, kind: ControllerKind) {
    setControllers((current) => ({
      ...current,
      [role]: kind === "openai" ? { ...DEFAULT_OPENAI_CONFIG } : { ...DEFAULT_HUMAN_CONFIG },
    }));
  }

  function updateControllerModel(role: string, model: string) {
    setControllers((current) => ({
      ...current,
      [role]: {
        ...current[role],
        model,
      },
    }));
  }

  function updateControllerReasoning(role: string, reasoningEffort: ReasoningEffort) {
    setControllers((current) => ({
      ...current,
      [role]: {
        ...current[role],
        reasoning_effort: reasoningEffort,
      },
    }));
  }

  const activeRoleKind = session?.active_controller.kind ?? "human";

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <p className="eyebrow">Codenames LLM</p>
        <h1>Mixed human and OpenAI play, backed by one game session API.</h1>
        <p className="lede">
          The browser, CLI, and future model-vs-model experiments now share the same
          stateful session core, controller contracts, and transcript data.
        </p>
        <form className="session-form" onSubmit={handleCreateSession}>
          <label>
            Starting team
            <select value={starts} onChange={(event) => setStarts(event.target.value as "red" | "blue")}>
              <option value="red">Red</option>
              <option value="blue">Blue</option>
            </select>
          </label>
          <label>
            Seed
            <input
              value={seed}
              onChange={(event) => setSeed(event.target.value)}
              inputMode="numeric"
              placeholder="Optional"
            />
          </label>
          <div className="controller-grid">
            {ROLE_KEYS.map((role) => (
              <fieldset className="controller-card" key={role}>
                <legend>{formatRole(role)}</legend>
                <label>
                  Controller
                  <select
                    value={controllers[role].kind}
                    onChange={(event) => updateControllerKind(role, event.target.value as ControllerKind)}
                  >
                    <option value="human">Human</option>
                    <option value="openai">OpenAI</option>
                  </select>
                </label>
                {controllers[role].kind === "openai" ? (
                  <>
                    <label>
                      Model
                      <input
                        value={controllers[role].model ?? ""}
                        onChange={(event) => updateControllerModel(role, event.target.value)}
                      />
                    </label>
                    <label>
                      Reasoning
                      <select
                        value={controllers[role].reasoning_effort ?? "low"}
                        onChange={(event) =>
                          updateControllerReasoning(role, event.target.value as ReasoningEffort)
                        }
                      >
                        <option value="none">None</option>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="xhigh">XHigh</option>
                      </select>
                    </label>
                  </>
                ) : null}
              </fieldset>
            ))}
          </div>
          <button type="submit" disabled={loading}>
            {loading ? "Creating..." : "Create session"}
          </button>
        </form>
        {session ? <p className="session-id">Session: {session.session_id}</p> : null}
        {error ? <p className="error-banner">{error}</p> : null}
      </section>

      {session ? (
        <section className="dashboard-grid">
          <article className="panel">
            <PanelTitle title="Status" subtitle="Polling every 2.5 seconds" />
            <StatusPanel session={session} />
          </article>

          <article className="panel panel--board">
            <PanelTitle title="Public Board" subtitle="Neutral until revealed" />
            <BoardGrid rows={session.public_board.rows} />
          </article>

          <article className="panel panel--board">
            <PanelTitle title="Spymaster Board" subtitle="All hidden roles visible" />
            <BoardGrid rows={session.spymaster_board.rows} showRoles />
          </article>

          <article className="panel">
            <PanelTitle
              title="Action Console"
              subtitle={
                activeRoleKind === "human"
                  ? "Manual controls for the active human role"
                  : "Backend-controlled OpenAI turn execution"
              }
            />
            {session.game.status === "game_over" ? (
              <p className="history-empty">Game over. No more actions are available.</p>
            ) : session.awaiting_human_input ? (
              session.game.phase === "clue" ? (
                <form className="action-form" onSubmit={handleClueSubmit}>
                  <label>
                    Clue word
                    <input
                      value={clueWord}
                      onChange={(event) => setClueWord(event.target.value)}
                      placeholder="single word"
                    />
                  </label>
                  <label>
                    Clue number
                    <input
                      value={clueNumber}
                      onChange={(event) => setClueNumber(event.target.value)}
                      inputMode="numeric"
                    />
                  </label>
                  <button type="submit">Submit clue</button>
                </form>
              ) : (
                <div className="action-stack">
                  <form className="action-form" onSubmit={handleGuessSubmit}>
                    <label>
                      Guess word
                      <input
                        value={guessWord}
                        onChange={(event) => setGuessWord(event.target.value)}
                        placeholder="board word"
                      />
                    </label>
                    <button type="submit">Submit guess</button>
                  </form>
                  <button className="secondary-button" type="button" onClick={handlePass}>
                    Pass turn
                  </button>
                </div>
              )
            ) : (
              <div className="action-stack">
                <p className="history-empty">
                  {formatRole(session.game.active_player)} is controlled by OpenAI.
                </p>
                <button type="button" onClick={handleAiStep} disabled={isAdvancingAi || !session.can_step}>
                  {isAdvancingAi ? "Stepping..." : "Step AI Turn"}
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={handleAiRun}
                  disabled={isAdvancingAi || !session.can_step}
                >
                  {isAdvancingAi ? "Running..." : "Run Until Human"}
                </button>
              </div>
            )}
          </article>

          <article className="panel panel--history">
            <PanelTitle title="Transcript" subtitle="Latest game events" />
            <HistoryList events={session.history} />
          </article>

          <article className="panel panel--history">
            <PanelTitle title="AI Trace" subtitle="Safe decision metadata only" />
            <AITraceList entries={session.ai_trace} />
          </article>

          <article className="panel panel--history">
            <PanelTitle title="Prompt Debug" subtitle="Latest request sent to OpenAI" />
            <PromptDebugPanel entries={session.ai_trace} />
          </article>
        </section>
      ) : (
        <section className="empty-panel">
          <p>Create a session to see the public board, spymaster board, status, and actions.</p>
        </section>
      )}
    </main>
  );
}

function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="panel-title">
      <h2>{title}</h2>
      <p>{subtitle}</p>
    </header>
  );
}

function StatusPanel({ session }: { session: SessionView }) {
  return (
    <dl className="status-grid">
      <div>
        <dt>Round</dt>
        <dd>{session.game.round_number}</dd>
      </div>
      <div>
        <dt>Turn</dt>
        <dd>{session.game.turn_number}</dd>
      </div>
      <div>
        <dt>Active team</dt>
        <dd>{session.game.active_team}</dd>
      </div>
      <div>
        <dt>Active role</dt>
        <dd>{session.game.active_player}</dd>
      </div>
      <div>
        <dt>Active controller</dt>
        <dd>{session.active_controller.kind}</dd>
      </div>
      <div>
        <dt>Phase</dt>
        <dd>{session.game.phase}</dd>
      </div>
      <div>
        <dt>Current clue</dt>
        <dd>
          {session.game.current_clue
            ? `${session.game.current_clue.word} ${session.game.current_clue.number}`
            : "none"}
        </dd>
      </div>
      <div>
        <dt>Guesses left</dt>
        <dd>{session.game.guesses_remaining ?? "n/a"}</dd>
      </div>
      <div>
        <dt>Winner</dt>
        <dd>{session.game.winner ?? "n/a"}</dd>
      </div>
      <div>
        <dt>Red agents</dt>
        <dd>{session.game.remaining_agents.red}</dd>
      </div>
      <div>
        <dt>Blue agents</dt>
        <dd>{session.game.remaining_agents.blue}</dd>
      </div>
      <div>
        <dt>Waiting on</dt>
        <dd>{session.awaiting_human_input ? "human" : "openai"}</dd>
      </div>
    </dl>
  );
}

function BoardGrid({
  rows,
  showRoles = false,
}: {
  rows: CardView[][];
  showRoles?: boolean;
}) {
  return (
    <div className="board-grid" data-testid="board-grid">
      {rows.map((row, rowIndex) => (
        <div className="board-row" key={`row-${rowIndex}`}>
          {row.map((card) => (
            <article
              className={`card ${CARD_CLASS_BY_COLOR[card.color]}`}
              key={`${card.index}-${card.word}`}
            >
              <span className="card-word">{card.word}</span>
              {showRoles && card.role ? <span className="card-role">{card.role}</span> : null}
            </article>
          ))}
        </div>
      ))}
    </div>
  );
}

function HistoryList({ events }: { events: HistoryEventView[] }) {
  if (events.length === 0) {
    return <p className="history-empty">No actions yet.</p>;
  }

  return (
    <ol className="history-list">
      {events.map((event, index) => (
        <li key={`${event.type}-${event.turn_number}-${event.round_number}-${index}`}>
          {formatHistoryEvent(event)}
        </li>
      ))}
    </ol>
  );
}

function AITraceList({ entries }: { entries: AITraceEntry[] }) {
  if (entries.length === 0) {
    return <p className="history-empty">No AI actions yet.</p>;
  }

  return (
    <ol className="history-list">
      {entries.map((entry) => (
        <li key={`trace-${entry.sequence}`}>
          {`#${entry.sequence}: ${entry.role} ${entry.action_type} via ${entry.controller.kind} (${entry.status})`}
        </li>
      ))}
    </ol>
  );
}

function PromptDebugPanel({ entries }: { entries: AITraceEntry[] }) {
  const latestEntryWithPrompt = [...entries].reverse().find((entry) => entry.prompt);
  if (!latestEntryWithPrompt?.prompt) {
    return <p className="history-empty">No AI prompt captured yet.</p>;
  }

  return (
    <div className="debug-panel">
      <p className="debug-meta">
        {`${latestEntryWithPrompt.role} ${latestEntryWithPrompt.action_type} via ${latestEntryWithPrompt.controller.kind}`}
      </p>
      <pre className="debug-prompt">{latestEntryWithPrompt.prompt}</pre>
    </div>
  );
}

function formatHistoryEvent(event: HistoryEventView): string {
  const prefix = `R${event.round_number} T${event.turn_number}`;
  if (event.type === "clue" && event.clue) {
    return `${prefix}: ${event.player} gave clue ${event.clue.word} ${event.clue.number}`;
  }
  if (event.type === "guess" && event.guessed_word && event.revealed_role) {
    const outcome = event.was_correct ? "correct" : "miss";
    return `${prefix}: ${event.player} guessed ${event.guessed_word} (${event.revealed_role}, ${outcome})`;
  }
  return `${prefix}: ${event.player} passed`;
}

function formatRole(role: string): string {
  return role.replaceAll("_", " ");
}
