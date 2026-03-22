import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useLocation, useParams } from "react-router";
import { BrutalistButton } from "../components/BrutalistButton";
import { BrutalistCard } from "../components/BrutalistCard";
import { PhilosopherIcon } from "../components/PhilosopherIcon";
import { DebateArena } from "../components/DebateArena";
import { InteractionBloomGraph } from "../components/InteractionBloomGraph";
import {
  ArrowLeft,
  TrendingUp,
  Send,
  Pause,
  Play,
  Loader2,
  AlertCircle,
  Flag,
  User,
  ThumbsUp,
  ThumbsDown,
  Minus,
  MessageSquare,
  Users,
  GitFork,
} from "lucide-react";

type ViewMode = "chat" | "arena" | "graph";
import { advanceSession, interjectSession, finishSession, personaColor, stanceLabel } from "../lib/api";
import type { SessionSnapshot, Message, PersonaStance } from "../lib/types";
import { PHILOSOPHERS } from "../data/philosophers";

const PHILOSOPHER_COLORS: Record<string, string> = Object.fromEntries(
  PHILOSOPHERS.map((p) => [p.id, p.color])
);
const PHILOSOPHER_SUBTITLE: Record<string, string> = Object.fromEntries(
  PHILOSOPHERS.map((p) => [p.id, p.stance])
);

function sentimentFromStance(stance: number | null): "for" | "against" | "undecided" {
  return stanceLabel(stance);
}

function SentimentBadge({ label, confidence }: { label: "for" | "against" | "undecided"; confidence?: number | null }) {
  const cfg = {
    for:       { bg: "#A7F3D0", icon: <ThumbsUp  className="w-3 h-3" />, text: "agree"    },
    against:   { bg: "#FCA5A5", icon: <ThumbsDown className="w-3 h-3" />, text: "disagree" },
    undecided: { bg: "#E0E0E0", icon: <Minus      className="w-3 h-3" />, text: "neutral"  },
  }[label];
  const pct = confidence != null ? Math.round(confidence * 100) : null;
  return (
    <div
      className="flex items-center gap-1 px-2 py-1 border-2 border-black text-xs font-medium flex-shrink-0"
      style={{ backgroundColor: cfg.bg }}
    >
      {cfg.icon}
      <span>{cfg.text}</span>
      {pct != null && <span className="opacity-60">{pct}%</span>}
    </div>
  );
}

export function Debate() {
  const { debateId: sessionId } = useParams<{ debateId: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const question: string = location.state?.question || sessionStorage.getItem("agora-question") || "";
  const initialSnapshot: SessionSnapshot | null = location.state?.snapshot ?? null;

  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(initialSnapshot);
  const [visibleMessages, setVisibleMessages] = useState<Message[]>(initialSnapshot?.messages ?? []);
  const [isPaused, setIsPaused] = useState(false);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [interjectText, setInterjectText] = useState("");
  const [isInterjecting, setIsInterjecting] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("chat");

  const isPausedRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const revealQueueRef = useRef<Message[]>([]);
  const revealTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seenMessageIds = useRef<Set<string>>(new Set((initialSnapshot?.messages ?? []).map((m) => m.id)));
  const hasRedirected = useRef(false);

  useEffect(() => {
    if ((!question || !sessionId) && !hasRedirected.current) {
      hasRedirected.current = true;
      navigate("/", { replace: true });
    }
  }, []);

  const enqueueMessages = useCallback((newMsgs: Message[]) => {
    const toAdd = newMsgs.filter((m) => !seenMessageIds.current.has(m.id));
    if (toAdd.length === 0) return;
    toAdd.forEach((m) => seenMessageIds.current.add(m.id));
    revealQueueRef.current.push(...toAdd);

    if (revealTimerRef.current !== null) return;

    const tick = () => {
      const msg = revealQueueRef.current.shift();
      if (!msg) { revealTimerRef.current = null; return; }
      setVisibleMessages((prev) => [...prev, msg]);
      revealTimerRef.current = setTimeout(tick, 700);
    };
    revealTimerRef.current = setTimeout(tick, 700);
  }, []);

  useEffect(() => {
    return () => { if (revealTimerRef.current) clearTimeout(revealTimerRef.current); };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visibleMessages]);

  useEffect(() => {
    if (!sessionId || !snapshot) return;
    if (isPausedRef.current) return;
    if (isAdvancing || isFinishing) return;
    if (snapshot.status === "complete") return;
    if (snapshot.current_round >= snapshot.round_goal) return;

    const delay = visibleMessages.length === 0 ? 500 : 1500;
    const timer = setTimeout(async () => {
      if (isPausedRef.current) return;
      setIsAdvancing(true);
      setError(null);
      try {
        const updated = await advanceSession(sessionId);
        setSnapshot(updated);
        enqueueMessages(updated.messages);
      } catch (e) {
        setError(`Advance failed: ${e instanceof Error ? e.message : "Unknown error"}`);
      } finally {
        setIsAdvancing(false);
      }
    }, delay);

    return () => clearTimeout(timer);
  }, [snapshot?.current_round, isAdvancing, isPaused, sessionId]);

  const handleTogglePause = () => {
    isPausedRef.current = !isPausedRef.current;
    setIsPaused((v) => !v);
  };

  const handleInterject = async () => {
    if (!interjectText.trim() || !sessionId) return;
    setIsInterjecting(true);
    setError(null);
    try {
      const updated = await interjectSession(sessionId, interjectText.trim());
      setSnapshot(updated);
      enqueueMessages(updated.messages);
      setInterjectText("");
    } catch (e) {
      setError(`Interjection failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setIsInterjecting(false);
    }
  };

  const handleFinish = async () => {
    if (!sessionId) return;
    // If the backend already auto-completed (brief is on the snapshot), navigate directly.
    if (snapshot?.status === "complete" && snapshot?.brief) {
      navigate(`/verdict/${sessionId}`, { state: { snapshot, question } });
      return;
    }
    setIsFinishing(true);
    setError(null);
    try {
      const final = await finishSession(sessionId);
      navigate(`/verdict/${sessionId}`, { state: { snapshot: final, question } });
    } catch (e) {
      setError(`Failed to generate verdict: ${e instanceof Error ? e.message : "Unknown error"}`);
      setIsFinishing(false);
    }
  };

  // Debate is active when still within rounds and not yet complete
  const isDebating = snapshot ? snapshot.status !== "complete" && snapshot.current_round < snapshot.round_goal : false;
  // Show the report button when all rounds are done — whether the backend auto-completed or we need to call finish
  const roundsDone = snapshot
    ? snapshot.status === "complete" || snapshot.current_round >= snapshot.round_goal
    : false;

  // Color lookup: philosopher color if known, else cycle by roster index
  const rosterMap = new Map<string, PersonaStance & { color: string }>();
  if (snapshot) {
    snapshot.roster.forEach((r, idx) => {
      const color = PHILOSOPHER_COLORS[r.persona_id] ?? personaColor(idx);
      rosterMap.set(r.persona_id, { ...r, color });
    });
  }

  function authorColor(authorId: string): string {
    return rosterMap.get(authorId)?.color ?? "#E8D5C4";
  }

  // Only show persona and user messages — skip system/frame messages
  const displayMessages = visibleMessages.filter((m) => m.role !== "system");

  // Derive live stances from visible messages so the bars update as each message is revealed.
  // For each persona, take the most recent message that has a non-null stance value.
  const liveStanceMap = new Map<string, { stance: number; confidence: number; label: "for" | "against" | "undecided" }>();
  // Seed with roster baseline first (so personas with no messages yet show initial stance)
  snapshot?.roster.forEach((r) => {
    liveStanceMap.set(r.persona_id, { stance: r.stance, confidence: r.confidence, label: r.label });
  });
  // Override with message-level stances (later messages win)
  displayMessages.forEach((m) => {
    if (m.role === "persona" && m.stance !== null && m.confidence !== null) {
      liveStanceMap.set(m.author_id, {
        stance: m.stance,
        confidence: m.confidence,
        label: stanceLabel(m.stance),
      });
    }
  });

  const liveRoster = snapshot?.roster.map((r) => ({
    ...r,
    ...(liveStanceMap.get(r.persona_id) ?? {}),
  })) ?? [];

  const forCount       = liveRoster.filter((r) => r.label === "for").length;
  const againstCount   = liveRoster.filter((r) => r.label === "against").length;
  const undecidedCount = liveRoster.filter((r) => r.label === "undecided").length;
  const rosterTotal    = liveRoster.length || 1;

  const latestPersonaMessage = [...displayMessages].reverse().find((m) => m.role === "persona") ?? null;

  const VIEW_TABS: { mode: ViewMode; label: string; icon: React.ReactNode }[] = [
    { mode: "chat",  label: "Chat",  icon: <MessageSquare className="w-3.5 h-3.5" /> },
    { mode: "arena", label: "Arena", icon: <Users         className="w-3.5 h-3.5" /> },
    { mode: "graph", label: "Graph", icon: <GitFork       className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Back */}
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 mb-6 hover:translate-x-[-2px] transition-transform"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </button>

        {/* Header */}
        <BrutalistCard variant="secondary" className="p-6 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-1">
                <h2>
                  {isAdvancing
                    ? `Round ${(snapshot?.current_round ?? 0) + 1} in Progress...`
                    : isPaused
                    ? "Debate Paused"
                    : isDebating
                    ? "Debate in Progress"
                    : roundsDone
                    ? "Rounds Complete"
                    : "Debate Concluded"}
                </h2>
                {snapshot && (
                  <span className="text-sm text-muted-foreground">
                    Round {snapshot.current_round}/{snapshot.round_goal}
                  </span>
                )}
              </div>
              <p className="text-lg">{question}</p>
            </div>
            {isDebating && (
              <button
                onClick={handleTogglePause}
                className="flex-shrink-0 flex items-center gap-2 border-[3px] border-black bg-white px-4 py-2 shadow-[3px_3px_0_0_#0A0A0A] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[2px_2px_0_0_#0A0A0A] transition-all"
              >
                {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                <span className="text-sm font-semibold">{isPaused ? "Resume" : "Pause"}</span>
              </button>
            )}
            {roundsDone && !isAdvancing && (
              <button
                onClick={handleFinish}
                disabled={isFinishing}
                className="flex-shrink-0 flex items-center gap-2 border-[3px] border-black bg-black text-white px-4 py-2 shadow-[3px_3px_0_0_#0A0A0A] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[2px_2px_0_0_#0A0A0A] transition-all disabled:opacity-60"
              >
                {isFinishing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Flag className="w-4 h-4" />}
                <span className="text-sm font-semibold">{isFinishing ? "Loading..." : "View Report"}</span>
              </button>
            )}
          </div>
        </BrutalistCard>

        {/* View toggle */}
        <div className="flex mb-4">
          {VIEW_TABS.map(({ mode, label, icon }, i) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`flex items-center gap-1.5 px-4 py-2 border-2 border-black text-sm font-semibold transition-all ${
                i > 0 ? "-ml-[2px]" : ""
              } ${
                viewMode === mode
                  ? "bg-black text-white z-10 relative"
                  : "bg-white hover:bg-[#F0EDE6]"
              }`}
            >
              {icon}
              {label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main content (3/4) */}
          <div className="lg:col-span-3 flex flex-col min-h-0">
            {/* CHAT VIEW */}
            {viewMode === "chat" && (
              <div
                className="border-4 border-black bg-white overflow-y-auto flex-1"
                style={{ maxHeight: "calc(100vh - 26rem)" }}
              >
                <div className="space-y-4 p-6">
                  {displayMessages.map((msg) => (
                    <div key={msg.id}>
                      {msg.role === "user" ? (
                        <div className="flex gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                          <div className="w-12 h-12 flex-shrink-0 flex items-center justify-center border-2 border-black bg-[#E8D5C4]">
                            <User className="w-6 h-6" />
                          </div>
                          <BrutalistCard className="flex-1 p-4 bg-[#F0EDE6]">
                            <div className="mb-2">
                              <h4 className="font-semibold">You</h4>
                              <p className="text-xs text-muted-foreground">Interjection</p>
                            </div>
                            <p>{msg.content}</p>
                          </BrutalistCard>
                        </div>
                      ) : (
                        <div className="flex gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                          <div
                            className="w-12 h-12 flex-shrink-0 flex items-center justify-center border-2 border-black"
                            style={{ backgroundColor: authorColor(msg.author_id) }}
                          >
                            <PhilosopherIcon philosopherId={msg.author_id} className="w-7 h-7" />
                          </div>
                          <BrutalistCard className="flex-1 p-4">
                            <div className="flex items-start justify-between mb-2 gap-3">
                              <div>
                                <h4 className="font-bold leading-tight">{msg.author_name}</h4>
                                {PHILOSOPHER_SUBTITLE[msg.author_id] && (
                                  <p className="text-xs text-muted-foreground">{PHILOSOPHER_SUBTITLE[msg.author_id]}</p>
                                )}
                              </div>
                              {msg.stance !== null && (
                                <SentimentBadge label={sentimentFromStance(msg.stance)} confidence={msg.confidence} />
                              )}
                            </div>
                            <p className="leading-relaxed">{msg.content}</p>
                          </BrutalistCard>
                        </div>
                      )}
                    </div>
                  ))}

                  {isAdvancing && (
                    <div className="flex items-center gap-3 py-4 px-2 text-muted-foreground text-sm">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Agents deliberating round {(snapshot?.current_round ?? 0) + 1}...</span>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              </div>
            )}

            {/* ARENA VIEW */}
            {viewMode === "arena" && (
              <DebateArena
                roster={liveRoster}
                latestMessage={latestPersonaMessage}
              />
            )}

            {/* GRAPH VIEW */}
            {viewMode === "graph" && (
              <InteractionBloomGraph
                roster={liveRoster}
                messages={displayMessages}
                networkEdges={snapshot?.network_edges ?? []}
                trajectories={snapshot?.trajectories ?? []}
                currentRound={snapshot?.current_round ?? 0}
                roundGoal={snapshot?.round_goal ?? 0}
              />
            )}

            {error && (
              <div className="p-3 bg-red-100 border-2 border-red-500 flex items-center gap-2 mt-2">
                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Interject */}
            <BrutalistCard className="p-4 bg-[#F0EDE6] mt-4">
              <label className="block mb-2 text-sm font-semibold">Interject in the debate</label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={interjectText}
                  onChange={(e) => setInterjectText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleInterject()}
                  placeholder="Add your perspective to the debate..."
                  className="flex-1 px-4 py-3 border-2 border-black bg-white focus:outline-none focus:ring-4 focus:ring-black/20"
                  disabled={isInterjecting}
                />
                <BrutalistButton
                  variant="primary"
                  size="sm"
                  onClick={handleInterject}
                  disabled={!interjectText.trim() || isInterjecting}
                  className={!interjectText.trim() ? "opacity-50 cursor-not-allowed" : ""}
                >
                  {isInterjecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </BrutalistButton>
              </div>
            </BrutalistCard>

          </div>

          {/* Right Sidebar */}
          <div className="lg:col-span-1 flex flex-col">
            <BrutalistCard className="p-6 sticky top-4 overflow-y-auto" style={{ maxHeight: "calc(100vh - 22rem)" }}>
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="w-5 h-5" />
                <h3 className="font-semibold">Live Sentiment</h3>
              </div>

              {/* Aggregate bars */}
              <div className="space-y-3 mb-6">
                {[
                  { label: "Agree",    count: forCount,       bg: "#A7F3D0", icon: <ThumbsUp  className="w-3.5 h-3.5" /> },
                  { label: "Disagree", count: againstCount,   bg: "#FCA5A5", icon: <ThumbsDown className="w-3.5 h-3.5" /> },
                  { label: "Neutral",  count: undecidedCount, bg: "#D0D0D0", icon: <Minus      className="w-3.5 h-3.5" /> },
                ].map(({ label, count, bg, icon }) => {
                  const pct = Math.round((count / rosterTotal) * 100);
                  return (
                    <div key={label}>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="flex items-center gap-1.5">{icon}{label}</span>
                        <span className="font-bold">{pct}%</span>
                      </div>
                      <div className="h-1.5 bg-[#E8E8E8] border border-black/20">
                        <div
                          className="h-full transition-all duration-500"
                          style={{ width: `${pct}%`, backgroundColor: bg }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Per-persona stance */}
              <div className="space-y-3 mb-4">
                {liveRoster.map((r) => {
                  const color = PHILOSOPHER_COLORS[r.persona_id] ?? rosterMap.get(r.persona_id)?.color ?? "#E8D5C4";
                  return (
                    <div key={r.persona_id}>
                      <div className="flex items-center gap-2 mb-1">
                        <PhilosopherIcon philosopherId={r.persona_id} className="w-4 h-4 flex-shrink-0" />
                        <span className="text-xs font-semibold truncate flex-1">{r.persona_name}</span>
                        <span
                          className="text-xs px-1.5 py-0.5 border border-black flex items-center gap-1"
                          style={{
                            backgroundColor: r.label === "for" ? "#A7F3D0" : r.label === "against" ? "#FCA5A5" : "#D0D0D0",
                          }}
                        >
                          {r.label === "for" ? <ThumbsUp className="w-2.5 h-2.5" /> : r.label === "against" ? <ThumbsDown className="w-2.5 h-2.5" /> : <Minus className="w-2.5 h-2.5" />}
                          {r.label === "for" ? "agree" : r.label === "against" ? "disagree" : "neutral"}
                        </span>
                      </div>
                      <div className="h-2 border border-black relative" style={{ backgroundColor: `${color}30` }}>
                        {/* center tick always visible */}
                        <div className="absolute top-0 h-full w-px bg-black/20" style={{ left: "50%" }} />
                        {/* stance fill — minimum 4% so it's always visible */}
                        <div
                          className="absolute top-0 h-full transition-all duration-700"
                          style={{
                            left: "50%",
                            width: `${Math.max(Math.abs(r.stance) * 50, 4)}%`,
                            transform: r.stance >= 0 ? "none" : "translateX(-100%)",
                            backgroundColor: color,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Stats */}
              <div className="pt-4 border-t-2 border-black/10 space-y-1.5 text-sm">
                <p className="text-xs text-muted-foreground font-medium mb-2">Debate Stats</p>
                <div className="flex justify-between">
                  <span>Messages:</span>
                  <span className="font-semibold">{displayMessages.length}</span>
                </div>
                <div className="flex justify-between">
                  <span>Status:</span>
                  <span className="font-semibold capitalize">
                    {snapshot?.status === "complete" ? "Concluded" : isAdvancing ? `Round ${(snapshot?.current_round ?? 0) + 1}` : snapshot?.status ?? "running"}
                  </span>
                </div>
              </div>

              {snapshot && (
                <div className="mt-4">
                  <p className="text-xs text-muted-foreground mb-1">Round progress</p>
                  <div className="h-3 bg-[#F0EDE6] border-2 border-black">
                    <div
                      className="h-full bg-black transition-all duration-700"
                      style={{ width: `${(snapshot.current_round / snapshot.round_goal) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </BrutalistCard>
          </div>
        </div>
      </div>
    </div>
  );
}
