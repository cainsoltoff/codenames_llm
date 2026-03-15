import { useEffect, useRef, useState } from "react";
import {
  advanceAiTurn,
  createSession,
  getSession,
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
  PromptPreset,
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
  prompt_preset: null,
};

const DEFAULT_OPENAI_CONFIG: ControllerConfig = {
  kind: "openai",
  model: "gpt-5.4",
  reasoning_effort: "low",
  prompt_preset: "base",
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
  const [heldTurn, setHeldTurn] = useState<{ roundNumber: number; turnNumber: number } | null>(null);

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
      setHeldTurn(null);
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
      setHeldTurn(null);
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
      setHeldTurn(null);
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
      setHeldTurn(null);
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
      setHeldTurn(null);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setIsAdvancingAi(false);
    }
  }

  async function handleAdvanceTurn() {
    if (!session) {
      return;
    }
    setIsAdvancingAi(true);
    setError(null);
    try {
      const nextSession = await advanceAiTurn(session.session_id);
      setSession(nextSession);
      setHeldTurn(getLatestCompletedTurn(nextSession));
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

  function updateControllerPromptPreset(role: string, promptPreset: PromptPreset) {
    setControllers((current) => ({
      ...current,
      [role]: {
        ...current[role],
        prompt_preset: promptPreset,
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
                    {role.includes("spymaster") ? (
                      <label>
                        Prompt style
                        <select
                          value={controllers[role].prompt_preset ?? "base"}
                          onChange={(event) =>
                            updateControllerPromptPreset(role, event.target.value as PromptPreset)
                          }
                        >
                          <option value="base">Base</option>
                          <option value="aggressive_cluegiver">Aggressive Cluegiver</option>
                        </select>
                      </label>
                    ) : null}
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
          <article className="panel panel--status">
            <PanelTitle title="Status" subtitle="Polling every 2.5 seconds" />
            <StatusPanel session={session} />
          </article>

          <article className="panel panel--spectator">
            <PanelTitle title="Spectator View" subtitle="Matchup, turn spotlight, and clue state" />
            <SpectatorPanel
              session={session}
              activeRoleKind={activeRoleKind}
              clueWord={clueWord}
              clueNumber={clueNumber}
              guessWord={guessWord}
              isAdvancingAi={isAdvancingAi}
              heldTurn={heldTurn}
              onClearHeldTurn={() => setHeldTurn(null)}
              onClueWordChange={setClueWord}
              onClueNumberChange={setClueNumber}
              onGuessWordChange={setGuessWord}
              onClueSubmit={handleClueSubmit}
              onGuessSubmit={handleGuessSubmit}
              onPass={handlePass}
              onAiStep={handleAiStep}
              onAiRun={handleAdvanceTurn}
            />
          </article>

          <article className="panel panel--board">
            <PanelTitle title="Public Board" subtitle="Neutral until revealed" />
            <BoardGrid rows={session.public_board.rows} />
          </article>

          <article className="panel panel--board">
            <PanelTitle title="Spymaster Board" subtitle="All hidden roles visible" />
            <BoardGrid rows={session.spymaster_board.rows} showRoles />
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
        <dd>{formatEnumLabel(session.game.active_team)}</dd>
      </div>
      <div>
        <dt>Active role</dt>
        <dd>{formatEnumLabel(session.game.active_player)}</dd>
      </div>
      <div>
        <dt>Active controller</dt>
        <dd>{formatEnumLabel(session.active_controller.kind)}</dd>
      </div>
      <div>
        <dt>Phase</dt>
        <dd>{formatEnumLabel(session.game.phase)}</dd>
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
        <dd>{session.game.winner ? formatEnumLabel(session.game.winner) : "n/a"}</dd>
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
        <dd>{formatEnumLabel(session.awaiting_human_input ? "human" : "openai")}</dd>
      </div>
    </dl>
  );
}

function SpectatorPanel({
  session,
  activeRoleKind,
  clueWord,
  clueNumber,
  guessWord,
  isAdvancingAi,
  heldTurn,
  onClearHeldTurn,
  onClueWordChange,
  onClueNumberChange,
  onGuessWordChange,
  onClueSubmit,
  onGuessSubmit,
  onPass,
  onAiStep,
  onAiRun,
}: {
  session: SessionView;
  activeRoleKind: "human" | "openai";
  clueWord: string;
  clueNumber: string;
  guessWord: string;
  isAdvancingAi: boolean;
  heldTurn: { roundNumber: number; turnNumber: number } | null;
  onClearHeldTurn: () => void;
  onClueWordChange: (value: string) => void;
  onClueNumberChange: (value: string) => void;
  onGuessWordChange: (value: string) => void;
  onClueSubmit: (event: React.FormEvent<HTMLFormElement>) => Promise<void>;
  onGuessSubmit: (event: React.FormEvent<HTMLFormElement>) => Promise<void>;
  onPass: () => Promise<void>;
  onAiStep: () => Promise<void>;
  onAiRun: () => Promise<void>;
}) {
  const redRoles = [
    { role: "red_spymaster", label: "Red Spymaster" },
    { role: "red_operative", label: "Red Operative" },
  ] as const;
  const blueRoles = [
    { role: "blue_spymaster", label: "Blue Spymaster" },
    { role: "blue_operative", label: "Blue Operative" },
  ] as const;
  const displayTurn = heldTurn
    ? buildHeldTurnView(session, heldTurn.roundNumber, heldTurn.turnNumber)
    : buildLiveTurnView(session);
  const activeTeamClassName =
    displayTurn.team === "red" ? "spotlight-card--team-red" : "spotlight-card--team-blue";

  return (
    <div className="spectator-panel">
      <div className="matchup-grid">
        <TeamLineup
          title="Red Team"
          teamClassName="lineup-card--red"
          roles={redRoles}
          displayTeam={displayTurn.team}
          session={session}
        />
        <TeamLineup
          title="Blue Team"
          teamClassName="lineup-card--blue"
          roles={blueRoles}
          displayTeam={displayTurn.team}
          session={session}
        />
      </div>

      <div className="turn-spotlight">
        <div className={`spotlight-card spotlight-card--active ${activeTeamClassName}`}>
          <span className="spotlight-label">{displayTurn.isHeld ? "Just Finished" : "Now Acting"}</span>
          <strong>{formatEnumLabel(displayTurn.player)}</strong>
          <span>{`${formatEnumLabel(displayTurn.team)} Team • ${displayTurn.phaseLabel}`}</span>
        </div>
        <div className={`spotlight-card spotlight-card--clue ${activeTeamClassName}`}>
          <span className="spotlight-label">Current Clue</span>
          <strong>
            {displayTurn.clue
              ? `${displayTurn.clue.word} ${displayTurn.clue.number}`
              : "Waiting for clue"}
          </strong>
          <span>
            {displayTurn.clue
              ? displayTurn.isHeld
                ? "Completed turn recap stays here until you advance again."
                : "Operatives are guessing from this clue."
              : "Spymaster clue phase is active."}
          </span>
        </div>
        <div className={`spotlight-card spotlight-card--guess ${activeTeamClassName}`}>
          <span className="spotlight-label">Guesses Remaining</span>
          <strong>{displayTurn.guessesRemaining ?? "n/a"}</strong>
          <span>
            {displayTurn.guessesRemaining === null
              ? "No guesses available until a clue is submitted."
              : displayTurn.isHeld
                ? "Remaining guesses when the turn ended."
                : "Includes the standard bonus guess."}
          </span>
        </div>
        <div className={`spotlight-card spotlight-card--history ${activeTeamClassName}`}>
          <span className="spotlight-label">Current Turn Guesses</span>
          {displayTurn.guesses.length > 0 ? (
            <ul className="spotlight-guess-list">
              {displayTurn.guesses.map((event, index) => (
                <li key={`${event.turn_number}-${event.round_number}-${event.guessed_word}-${index}`}>
                  <strong>{event.guessed_word}</strong>
                  <span>{`${formatEnumLabel(event.revealed_role ?? "")} • ${event.was_correct ? "Correct" : "Miss"}`}</span>
                </li>
              ))}
            </ul>
          ) : (
            <strong>No guesses yet</strong>
          )}
          <span>
            {displayTurn.guesses.length > 0
              ? displayTurn.isHeld
                ? "These are the guesses from the completed turn."
                : "Only guesses from the active turn are shown here."
              : "This fills in once the operative starts guessing."}
          </span>
        </div>
      </div>

      <div className="spectator-actions">
        <div className="spectator-actions-header">
          <strong>Action Console</strong>
          <span>
            {activeRoleKind === "human"
              ? "Manual controls for the active human role"
              : "Backend-controlled OpenAI turn execution"}
          </span>
        </div>
        {session.game.status === "game_over" ? (
          <p className="history-empty">Game over. No more actions are available.</p>
        ) : heldTurn ? (
          <div className="action-stack">
            <p className="history-empty">
              {`${formatEnumLabel(displayTurn.team)} Team turn complete. Click Advance Turn to move on.`}
            </p>
            {session.awaiting_human_input ? (
              <div className="action-stack">
                <p className="history-empty">
                  {`Next up: ${formatRole(session.game.active_player)} needs human input.`}
                </p>
                <button className="secondary-button" type="button" onClick={onClearHeldTurn}>
                  Continue to Human Turn
                </button>
              </div>
            ) : (
              <button
                className="secondary-button"
                type="button"
                onClick={onAiRun}
                disabled={isAdvancingAi || !session.can_step}
              >
                {isAdvancingAi ? "Advancing..." : "Advance Turn"}
              </button>
            )}
          </div>
        ) : session.awaiting_human_input ? (
          session.game.phase === "clue" ? (
            <form className="action-form" onSubmit={onClueSubmit}>
              <label>
                Clue word
                <input
                  value={clueWord}
                  onChange={(event) => onClueWordChange(event.target.value)}
                  placeholder="single word"
                />
              </label>
              <label>
                Clue number
                <input
                  value={clueNumber}
                  onChange={(event) => onClueNumberChange(event.target.value)}
                  inputMode="numeric"
                />
              </label>
              <button type="submit">Submit clue</button>
            </form>
          ) : (
            <div className="action-stack">
              <form className="action-form" onSubmit={onGuessSubmit}>
                <label>
                  Guess word
                  <input
                    value={guessWord}
                    onChange={(event) => onGuessWordChange(event.target.value)}
                    placeholder="board word"
                  />
                </label>
                <button type="submit">Submit guess</button>
              </form>
              <button className="secondary-button" type="button" onClick={onPass}>
                Pass turn
              </button>
            </div>
          )
        ) : (
          <div className="action-stack">
            <p className="history-empty">
              {formatRole(session.game.active_player)} is controlled by OpenAI.
            </p>
            <button type="button" onClick={onAiStep} disabled={isAdvancingAi || !session.can_step}>
              {isAdvancingAi ? "Stepping..." : "Step AI Turn"}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={onAiRun}
              disabled={isAdvancingAi || !session.can_step}
            >
              {isAdvancingAi ? "Advancing..." : "Advance Turn"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function TeamLineup({
  title,
  teamClassName,
  roles,
  displayTeam,
  session,
}: {
  title: string;
  teamClassName: string;
  roles: readonly { role: string; label: string }[];
  displayTeam: "red" | "blue";
  session: SessionView;
}) {
  return (
    <section className={`lineup-card ${teamClassName}`}>
      <h3>{title}</h3>
      <div className="lineup-roles">
        {roles.map(({ role, label }) => {
          const controller = session.controllers[role];
          const isActive = role.startsWith(displayTeam);
          return (
            <div className={`lineup-role ${isActive ? "lineup-role--active" : ""}`} key={role}>
              <span className="lineup-role-label">{label}</span>
              <strong>{formatControllerLabel(controller)}</strong>
            </div>
          );
        })}
      </div>
    </section>
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
              {showRoles && card.role ? <span className="card-role">{formatCardRole(card.role)}</span> : null}
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

  const orderedEvents = [...events].reverse();
  const latestRound = orderedEvents[0]?.round_number;
  const groupedEvents = orderedEvents.reduce<Array<{ round: number; events: HistoryEventView[] }>>(
    (groups, event) => {
      const existingGroup = groups.find((group) => group.round === event.round_number);
      if (existingGroup) {
        existingGroup.events.push(event);
      } else {
        groups.push({ round: event.round_number, events: [event] });
      }
      return groups;
    },
    [],
  );
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    containerRef.current.scrollTop = 0;
  }, [events]);

  return (
    <div className="history-feed" ref={containerRef}>
      {groupedEvents.map((group) => (
        <details
          className="history-round"
          key={`round-${group.round}`}
          open={group.round === latestRound}
        >
          <summary className="history-round-summary">
            <span>{`Round ${group.round}`}</span>
            <span>{`${group.events.length} event${group.events.length === 1 ? "" : "s"}`}</span>
          </summary>
          <ol className="history-list">
            {group.events.map((event, index) => {
              const isLatest = group.round === latestRound && index === 0;
              return (
                <li
                  className={`history-event history-event--${event.type} ${isLatest ? "history-event--latest" : ""}`}
                  key={`${event.type}-${event.turn_number}-${event.round_number}-${index}`}
                >
                  <div className="history-event-meta">
                    <span className="history-event-badge">{formatEventLabel(event.type)}</span>
                    {isLatest ? <span className="history-event-latest">Latest</span> : null}
                  </div>
                  <span>{formatHistoryEvent(event)}</span>
                </li>
              );
            })}
          </ol>
        </details>
      ))}
    </div>
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
          {`#${entry.sequence}: ${formatEnumLabel(entry.role)} ${formatEnumLabel(entry.action_type)} via ${formatEnumLabel(entry.controller.kind)} (${formatEnumLabel(entry.status)})`}
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
        {`${formatEnumLabel(latestEntryWithPrompt.role)} ${formatEnumLabel(latestEntryWithPrompt.action_type)} via ${formatEnumLabel(latestEntryWithPrompt.controller.kind)}`}
      </p>
      <pre className="debug-prompt">{latestEntryWithPrompt.prompt}</pre>
    </div>
  );
}

function formatHistoryEvent(event: HistoryEventView): string {
  const prefix = `R${event.round_number} T${event.turn_number}`;
  if (event.type === "clue" && event.clue) {
    return `${prefix}: ${formatEnumLabel(event.player)} gave clue ${event.clue.word} ${event.clue.number}`;
  }
  if (event.type === "guess" && event.guessed_word && event.revealed_role) {
    const outcome = event.was_correct ? "Correct" : "Miss";
    return `${prefix}: ${formatEnumLabel(event.player)} guessed ${event.guessed_word} (${formatEnumLabel(event.revealed_role)}, ${outcome})`;
  }
  return `${prefix}: ${formatEnumLabel(event.player)} passed`;
}

function formatEventLabel(eventType: HistoryEventView["type"]): string {
  return formatEnumLabel(eventType);
}

function formatRole(role: string): string {
  return formatEnumLabel(role);
}

function formatCardRole(role: string): string {
  return formatRole(role);
}

function formatControllerLabel(controller: ControllerConfig): string {
  return controller.kind === "openai" ? "GPT" : "Human";
}

function getLatestCompletedTurn(session: SessionView): { roundNumber: number; turnNumber: number } | null {
  const latestEvent = session.history[session.history.length - 1];
  if (!latestEvent) {
    return null;
  }
  return {
    roundNumber: latestEvent.round_number,
    turnNumber: latestEvent.turn_number,
  };
}

function buildLiveTurnView(session: SessionView) {
  return {
    team: session.game.active_team,
    player: session.game.active_player,
    clue: session.game.current_clue,
    guessesRemaining: session.game.guesses_remaining,
    guesses: session.history.filter(
      (event) =>
        event.type === "guess" &&
        event.round_number === session.game.round_number &&
        event.turn_number === session.game.turn_number,
    ),
    phaseLabel: `${formatEnumLabel(session.game.phase)} Phase`,
    isHeld: false,
  };
}

function buildHeldTurnView(
  session: SessionView,
  roundNumber: number,
  turnNumber: number,
) {
  const turnEvents = session.history.filter(
    (event) => event.round_number === roundNumber && event.turn_number === turnNumber,
  );
  const firstEvent = turnEvents[0];
  const clueEvent = turnEvents.find((event) => event.type === "clue");
  const guessEvents = turnEvents.filter((event) => event.type === "guess");
  const clue = clueEvent?.clue ?? null;
  const guessAllowance = clue ? clue.number + 1 : null;
  return {
    team: firstEvent?.team ?? session.game.active_team,
    player: clueEvent?.player ?? firstEvent?.player ?? session.game.active_player,
    clue,
    guessesRemaining:
      guessAllowance === null ? null : Math.max(guessAllowance - guessEvents.length, 0),
    guesses: guessEvents,
    phaseLabel: "Turn Complete",
    isHeld: true,
  };
}

function formatEnumLabel(value: string): string {
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
