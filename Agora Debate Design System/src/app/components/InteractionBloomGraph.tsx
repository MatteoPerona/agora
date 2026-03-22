import { useEffect, useState } from "react";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Crosshair,
  Pause,
  Play,
  Sparkles,
  Target,
  UserRound,
  Zap,
} from "lucide-react";
import { GreekIllustration } from "./GreekIllustration";
import { PhilosopherIcon } from "./PhilosopherIcon";
import type { Message, NetworkEdge, PersonaStance, TrajectorySeries } from "../lib/types";
import { PHILOSOPHERS } from "../data/philosophers";

const GRAPH_WIDTH = 1000;
const GRAPH_HEIGHT = 620;
const USER_NODE = { x: 500, y: 54 };

const SPRITE_FOLDER: Record<string, string> = {
  socrates: "socrates",
  epicurus: "epicurus",
  diogenes: "Diogenes",
  aristotle: "aristotle",
  seneca: "seneca",
  marcus: "marcus",
};

const FALLBACK_SPRITES = ["1", "2", "3"];

const PHILOSOPHER_COLORS: Record<string, string> = Object.fromEntries(
  PHILOSOPHERS.map((p) => [p.id, p.color])
);

const POSITION_PRESETS: Record<number, Array<{ x: number; y: number }>> = {
  1: [{ x: 500, y: 318 }],
  2: [
    { x: 240, y: 318 },
    { x: 760, y: 318 },
  ],
  3: [
    { x: 225, y: 185 },
    { x: 775, y: 185 },
    { x: 500, y: 470 },
  ],
  4: [
    { x: 230, y: 180 },
    { x: 770, y: 180 },
    { x: 230, y: 455 },
    { x: 770, y: 455 },
  ],
  5: [
    { x: 175, y: 205 },
    { x: 500, y: 118 },
    { x: 825, y: 205 },
    { x: 320, y: 485 },
    { x: 680, y: 485 },
  ],
  6: [
    { x: 175, y: 175 },
    { x: 500, y: 90 },
    { x: 825, y: 175 },
    { x: 175, y: 460 },
    { x: 500, y: 545 },
    { x: 825, y: 460 },
  ],
};

type PositionedRoster = PersonaStance & {
  x: number;
  y: number;
  color: string;
  spriteFolder: string;
};

type RoutedMessage = Message & {
  inferredTargets: string[];
};

interface InteractionBloomGraphProps {
  roster: PersonaStance[];
  messages: Message[];
  networkEdges: NetworkEdge[];
  trajectories: TrajectorySeries[];
  currentRound: number;
  roundGoal: number;
}

function getSpriteFolder(personaId: string, fallbackIndex: number): string {
  return SPRITE_FOLDER[personaId] ?? FALLBACK_SPRITES[fallbackIndex % FALLBACK_SPRITES.length];
}

function buildPositions(count: number): Array<{ x: number; y: number }> {
  const preset = POSITION_PRESETS[count];
  if (preset) return preset;

  return Array.from({ length: count }, (_, index) => {
    const angle = (-Math.PI / 2) + (index / Math.max(count, 1)) * Math.PI * 2;
    return {
      x: 500 + Math.cos(angle) * 350,
      y: 315 + Math.sin(angle) * 235,
    };
  });
}

function uniqueIds(values: string[]): string[] {
  return Array.from(new Set(values));
}

function edgeKey(sourceId: string, targetId: string): string {
  return `${sourceId}->${targetId}`;
}

function inferTargets(
  message: Message,
  index: number,
  messages: Message[],
  networkEdges: NetworkEdge[],
  personaIds: string[],
): string[] {
  if (message.role === "user") return personaIds;
  if (message.role !== "persona") return [];

  const explicit = uniqueIds(
    networkEdges
      .filter((edge) => edge.source_id === message.author_id && personaIds.includes(edge.target_id))
      .map((edge) => edge.target_id)
      .filter((targetId) => targetId !== message.author_id)
  );

  const nextSpeaker = messages
    .slice(index + 1)
    .find((candidate) => candidate.role === "persona" && candidate.author_id !== message.author_id);

  if (explicit.length > 0) {
    return uniqueIds([
      ...explicit,
      ...(nextSpeaker ? [nextSpeaker.author_id] : []),
    ]);
  }

  if (nextSpeaker) return [nextSpeaker.author_id];
  return personaIds.filter((personaId) => personaId !== message.author_id);
}

function buildCurvePath(source: { x: number; y: number }, target: { x: number; y: number }, seed: number): string {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy) || 1;
  const midpointX = (source.x + target.x) / 2;
  const midpointY = (source.y + target.y) / 2;
  const normalX = -dy / distance;
  const normalY = dx / distance;
  const bend = Math.min(90, distance * 0.18) * (seed % 2 === 0 ? 1 : -1);
  const controlX = midpointX + normalX * bend;
  const controlY = midpointY + normalY * bend;
  return `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function previewText(content: string, maxLength = 120): string {
  if (content.length <= maxLength) return content;
  return `${content.slice(0, maxLength - 1)}…`;
}

function sparklinePath(points: Array<{ round_index: number; stance: number }>, width = 220, height = 66): string {
  if (points.length === 0) {
    return `M 0 ${height / 2} L ${width} ${height / 2}`;
  }

  const lastRound = Math.max(...points.map((point) => point.round_index), 1);
  return points
    .map((point, index) => {
      const x = lastRound === 0 ? 0 : (point.round_index / lastRound) * width;
      const y = height - (((point.stance + 1) / 2) * height);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function InteractionBloomGraph({
  roster,
  messages,
  networkEdges,
  trajectories,
  currentRound,
  roundGoal,
}: InteractionBloomGraphProps) {
  const [activeMessageIndex, setActiveMessageIndex] = useState(0);
  const [isAutoplay, setIsAutoplay] = useState(true);
  const [focusedPersonaId, setFocusedPersonaId] = useState<string | null>(null);

  const positions = buildPositions(roster.length);
  const positionedRoster: PositionedRoster[] = roster.map((persona, index) => ({
    ...persona,
    x: positions[index]?.x ?? 500,
    y: positions[index]?.y ?? 310,
    color: PHILOSOPHER_COLORS[persona.persona_id] ?? "#6BFFD8",
    spriteFolder: getSpriteFolder(persona.persona_id, index),
  }));

  const personaIds = positionedRoster.map((persona) => persona.persona_id);
  const routedMessages: RoutedMessage[] = messages.map((message, index) => ({
    ...message,
    inferredTargets: inferTargets(message, index, messages, networkEdges, personaIds),
  }));
  const interactiveMessages = routedMessages.filter((message) => message.role === "persona" || message.role === "user");

  useEffect(() => {
    if (interactiveMessages.length === 0) {
      setActiveMessageIndex(0);
      return;
    }
    setActiveMessageIndex(interactiveMessages.length - 1);
  }, [interactiveMessages.length]);

  useEffect(() => {
    if (!isAutoplay || interactiveMessages.length <= 1) return;
    const timer = setInterval(() => {
      setActiveMessageIndex((current) => (current + 1) % interactiveMessages.length);
    }, 2600);
    return () => clearInterval(timer);
  }, [isAutoplay, interactiveMessages.length]);

  const activeMessage = interactiveMessages[activeMessageIndex] ?? null;
  const effectiveFocusId =
    focusedPersonaId ?? (activeMessage?.role === "persona" ? activeMessage.author_id : positionedRoster[0]?.persona_id ?? null);
  const selectedPersona =
    positionedRoster.find((persona) => persona.persona_id === effectiveFocusId) ?? positionedRoster[0] ?? null;
  const selectedTrajectory =
    trajectories.find((series) => series.persona_id === selectedPersona?.persona_id)?.points ?? [];

  const displayEdges = uniqueIds(
    (networkEdges.length > 0
      ? networkEdges
          .filter((edge) => personaIds.includes(edge.source_id) && personaIds.includes(edge.target_id))
          .map((edge) => edgeKey(edge.source_id, edge.target_id))
      : positionedRoster.flatMap((persona, index) => {
          const next = positionedRoster[(index + 1) % positionedRoster.length];
          if (!next || next.persona_id === persona.persona_id) return [];
          return [edgeKey(persona.persona_id, next.persona_id)];
        }))
  ).map((key) => {
    const [sourceId, targetId] = key.split("->");
    return { sourceId, targetId };
  });

  const edgeTraffic = new Map<string, number>();
  interactiveMessages.forEach((message) => {
    const sourceId = message.role === "user" ? "user" : message.author_id;
    message.inferredTargets.forEach((targetId) => {
      const key = edgeKey(sourceId, targetId);
      edgeTraffic.set(key, (edgeTraffic.get(key) ?? 0) + 1);
    });
  });

  const activeRoutes = activeMessage
    ? activeMessage.inferredTargets.map((targetId) => ({
        sourceId: activeMessage.role === "user" ? "user" : activeMessage.author_id,
        targetId,
      }))
    : [];

  const leaderboard = positionedRoster
    .map((persona) => {
      const personaTrajectory =
        trajectories.find((series) => series.persona_id === persona.persona_id)?.points ?? [];
      const sent = interactiveMessages.filter((message) => message.author_id === persona.persona_id).length;
      const received = interactiveMessages.filter((message) => message.inferredTargets.includes(persona.persona_id)).length;
      const volatility =
        personaTrajectory.length > 1
          ? Math.abs(
              (personaTrajectory.at(-1)?.stance ?? persona.stance) -
                (personaTrajectory[0]?.stance ?? persona.stance)
            )
          : Math.abs(persona.stance);
      const score = sent * 16 + received * 9 + Math.round(persona.confidence * 35) + Math.round(volatility * 40);
      return { persona, sent, received, score };
    })
    .sort((left, right) => right.score - left.score);

  const averageCurrentStance =
    positionedRoster.reduce((sum, persona) => sum + persona.stance, 0) / Math.max(positionedRoster.length, 1);
  const averageOpeningStance =
    trajectories.reduce((sum, series) => sum + (series.points[0]?.stance ?? 0), 0) /
    Math.max(trajectories.length, 1);
  const consensusDrift = Math.round(Math.abs(averageCurrentStance - averageOpeningStance) * 100);
  const heatIndex = Math.round(
    positionedRoster.reduce((sum, persona) => sum + Math.abs(persona.stance) * persona.confidence, 0) *
      (100 / Math.max(positionedRoster.length, 1))
  );

  const activeMessageColor =
    activeMessage?.role === "user"
      ? "#FFB347"
      : positionedRoster.find((persona) => persona.persona_id === activeMessage?.author_id)?.color ?? "#4FE5FF";

  const transmissionMode =
    !activeMessage
      ? "idle"
      : activeMessage.role === "user"
      ? "broadcast"
      : activeMessage.inferredTargets.length > 2
      ? "broadcast"
      : activeMessage.inferredTargets.length > 1
      ? "mesh"
      : "direct";

  return (
    <div
      className="overflow-hidden border-4 border-black bg-[#F7F0E5] text-[#0A0A0A]"
      style={{ minHeight: 760 }}
    >
      <style>{`
        @keyframes bloom-sweep {
          0% { transform: translateY(-30%); opacity: 0; }
          12% { opacity: 0.35; }
          50% { opacity: 0.12; }
          100% { transform: translateY(120%); opacity: 0; }
        }
        @keyframes bloom-spin {
          from { transform: translate(-50%, -50%) rotate(0deg); }
          to { transform: translate(-50%, -50%) rotate(360deg); }
        }
        @keyframes bloom-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.22; }
        }
      `}</style>

      <div className="relative">
        <div
          className="pointer-events-none absolute inset-0 opacity-50"
          style={{
            backgroundImage:
              "linear-gradient(rgba(10,10,10,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(10,10,10,0.06) 1px, transparent 1px)",
            backgroundSize: "30px 30px",
          }}
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-90"
          style={{
            background:
              "radial-gradient(circle at 50% 38%, rgba(232,255,139,0.48), transparent 26%), linear-gradient(135deg, rgba(255,107,157,0.14), transparent 38%), linear-gradient(320deg, rgba(107,157,255,0.10), transparent 30%)",
          }}
        />
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-44"
          style={{
            background: "linear-gradient(180deg, rgba(232,255,139,0.42), transparent)",
            animation: "bloom-sweep 8s linear infinite",
          }}
        />

        <div className="relative z-10 grid gap-4 p-4 xl:grid-cols-[minmax(0,1.7fr)_340px]">
          <section className="min-w-0 border-[3px] border-black bg-[#FCF8F1]/95 p-3 shadow-[4px_4px_0_0_#0A0A0A]">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-black/15 pb-3">
              <div>
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.35em] text-[#6B6B6B]">
                  <GreekIllustration type="pediment" className="h-4 w-8" />
                  Council Relay Map
                </div>
                <p className="mt-1 max-w-3xl text-xs text-[#6B6B6B]">
                  Speech paths, persuasion drift, and reply pressure across the agora floor.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => {
                    setIsAutoplay(false);
                    setActiveMessageIndex((current) => clamp(current - 1, 0, Math.max(interactiveMessages.length - 1, 0)));
                  }}
                  disabled={interactiveMessages.length === 0}
                  className="flex items-center gap-1 border-[2px] border-black bg-white px-3 py-2 text-xs font-mono uppercase tracking-[0.2em] shadow-[2px_2px_0_0_#0A0A0A] transition hover:translate-x-px hover:translate-y-px hover:shadow-[1px_1px_0_0_#0A0A0A] disabled:opacity-40"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  Prev
                </button>
                <button
                  onClick={() => setIsAutoplay((current) => !current)}
                  disabled={interactiveMessages.length <= 1}
                  className="flex items-center gap-1 border-[2px] border-black bg-[#E8FF8B] px-3 py-2 text-xs font-mono uppercase tracking-[0.2em] shadow-[2px_2px_0_0_#0A0A0A] transition hover:translate-x-px hover:translate-y-px hover:shadow-[1px_1px_0_0_#0A0A0A] disabled:opacity-40"
                >
                  {isAutoplay ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                  {isAutoplay ? "Freeze" : "Play"}
                </button>
                <button
                  onClick={() => {
                    setIsAutoplay(false);
                    setActiveMessageIndex((current) => clamp(current + 1, 0, Math.max(interactiveMessages.length - 1, 0)));
                  }}
                  disabled={interactiveMessages.length === 0}
                  className="flex items-center gap-1 border-[2px] border-black bg-white px-3 py-2 text-xs font-mono uppercase tracking-[0.2em] shadow-[2px_2px_0_0_#0A0A0A] transition hover:translate-x-px hover:translate-y-px hover:shadow-[1px_1px_0_0_#0A0A0A] disabled:opacity-40"
                >
                  Next
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div className="mt-3 grid gap-2 md:grid-cols-4">
              {[
                { label: "Packets", value: `${interactiveMessages.length}`, accent: "#4FE5FF", icon: <Zap className="h-3.5 w-3.5" /> },
                { label: "Consensus Drift", value: `${consensusDrift}%`, accent: "#FFB347", icon: <Target className="h-3.5 w-3.5" /> },
                { label: "Heat Index", value: `${heatIndex}%`, accent: "#7DFFA7", icon: <Activity className="h-3.5 w-3.5" /> },
                { label: "Round", value: `${currentRound}/${roundGoal}`, accent: "#FF6B9D", icon: <Sparkles className="h-3.5 w-3.5" /> },
              ].map((metric) => (
                <div
                  key={metric.label}
                  className="border-[2px] border-black px-3 py-2 shadow-[2px_2px_0_0_#0A0A0A]"
                  style={{
                    background: `linear-gradient(135deg, ${metric.accent}22, rgba(255,255,255,0.85))`,
                  }}
                >
                  <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.25em] text-[#6B6B6B]">
                    {metric.icon}
                    {metric.label}
                  </div>
                  <div className="mt-1 text-lg font-semibold text-black">{metric.value}</div>
                </div>
              ))}
            </div>

            <div className="relative mt-3 overflow-hidden border-[3px] border-black bg-[#F8F2E7]" style={{ height: 540 }}>
              <div
                className="pointer-events-none absolute left-1/2 top-1/2 h-[22rem] w-[22rem] rounded-full opacity-60"
                style={{
                  background: "conic-gradient(from 0deg, rgba(255,107,157,0.18), transparent 18%, transparent 100%)",
                  animation: "bloom-spin 12s linear infinite",
                }}
              />
              <div
                className="pointer-events-none absolute inset-0 opacity-55"
                style={{
                  backgroundImage:
                    "linear-gradient(rgba(10,10,10,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(10,10,10,0.04) 1px, transparent 1px)",
                  backgroundSize: "26px 26px",
                }}
              />
              <div className="pointer-events-none absolute left-1/2 top-[4.5rem] -translate-x-1/2 text-black/12">
                <GreekIllustration type="laurel" className="h-28 w-28" />
              </div>
              <div className="pointer-events-none absolute bottom-2 right-3 text-black/10">
                <GreekIllustration type="pediment" className="h-10 w-20" />
              </div>

              <svg viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`} className="absolute inset-0 h-full w-full">
                <defs>
                  <filter id="graphGlow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="1.8" result="coloredBlur" />
                    <feMerge>
                      <feMergeNode in="coloredBlur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                {[180, 280, 380].map((radius) => (
                  <circle
                    key={radius}
                    cx="500"
                    cy="310"
                    r={radius}
                    fill="none"
                    stroke="rgba(10,10,10,0.09)"
                    strokeDasharray="6 8"
                  />
                ))}

                {displayEdges.map((edge, index) => {
                  const source = positionedRoster.find((persona) => persona.persona_id === edge.sourceId);
                  const target = positionedRoster.find((persona) => persona.persona_id === edge.targetId);
                  if (!source || !target) return null;

                  const traffic = edgeTraffic.get(edgeKey(edge.sourceId, edge.targetId)) ?? 0;
                  const isFocused =
                    effectiveFocusId != null &&
                    (edge.sourceId === effectiveFocusId || edge.targetId === effectiveFocusId);
                  const path = buildCurvePath(source, target, index);
                  const active = activeRoutes.some(
                    (route) => route.sourceId === edge.sourceId && route.targetId === edge.targetId
                  );

                  return (
                    <g key={edgeKey(edge.sourceId, edge.targetId)}>
                      <path
                        d={path}
                        fill="none"
                        stroke={active ? activeMessageColor : "rgba(10,10,10,0.18)"}
                        strokeWidth={active ? 3 : 1 + Math.min(traffic, 4) * 0.45}
                        strokeDasharray={active ? "0" : "7 10"}
                        opacity={active ? 0.92 : isFocused ? 0.5 : 0.24}
                        filter={active ? "url(#graphGlow)" : undefined}
                      />
                    </g>
                  );
                })}

                {activeRoutes.map((route, routeIndex) => {
                  const source =
                    route.sourceId === "user"
                      ? USER_NODE
                      : positionedRoster.find((persona) => persona.persona_id === route.sourceId);
                  const target = positionedRoster.find((persona) => persona.persona_id === route.targetId);
                  if (!source || !target) return null;

                  const path = buildCurvePath(source, target, routeIndex + 7);
                  const duration = clamp(1.8 + routeIndex * 0.18, 1.8, 2.8);

                  return (
                    <g key={`${route.sourceId}-${route.targetId}-${activeMessage?.id ?? routeIndex}`}>
                      {[0, 0.72].map((delay, packetIndex) => (
                        <circle
                          key={delay}
                          r={packetIndex === 0 ? 5.5 : 3.5}
                          fill={activeMessageColor}
                          opacity={packetIndex === 0 ? 1 : 0.65}
                          filter="url(#graphGlow)"
                        >
                          <animateMotion
                            begin={`${delay}s`}
                            dur={`${duration}s`}
                            path={path}
                            repeatCount="indefinite"
                          />
                        </circle>
                      ))}
                    </g>
                  );
                })}

                {activeRoutes
                  .filter((route) => route.sourceId === "user")
                  .map((route) => {
                    const target = positionedRoster.find((persona) => persona.persona_id === route.targetId);
                    if (!target) return null;
                    const path = buildCurvePath(USER_NODE, target, 11);
                    return (
                      <path
                        key={`uplink-${route.targetId}`}
                        d={path}
                        fill="none"
                        stroke="#FFB347"
                        strokeWidth={2.25}
                        strokeDasharray="2 8"
                        opacity={0.75}
                        filter="url(#graphGlow)"
                      />
                    );
                  })}
              </svg>

              <div className="pointer-events-none absolute left-1/2 top-1/2 w-[15rem] -translate-x-1/2 -translate-y-1/2 border-[3px] border-black bg-white/92 p-4 text-center shadow-[4px_4px_0_0_#0A0A0A]">
                <div className="flex items-center justify-center gap-2 text-[11px] uppercase tracking-[0.32em] text-[#6B6B6B]">
                  <GreekIllustration type="column" className="h-4 w-4" />
                  Forum Center
                  <GreekIllustration type="column" className="h-4 w-4" />
                </div>
                <div className="mt-2 text-sm font-semibold text-black">
                  {activeMessage ? `${transmissionMode.toUpperCase()} EXCHANGE` : "WAITING FOR TRAFFIC"}
                </div>
                <div className="mt-2 font-mono text-xs text-[#6B6B6B]">
                  {activeMessage
                    ? `${activeMessage.role === "user" ? "UPLINK" : activeMessage.author_name.toUpperCase()} :: R${activeMessage.round_index}`
                    : "NO LIVE MESSAGE SELECTED"}
                </div>
                <div className="mt-3 h-1.5 overflow-hidden border border-black/20 bg-[#F0EDE6]">
                  <div
                    className="h-full"
                    style={{
                      width: activeMessage ? `${Math.min(100, 26 + activeMessage.inferredTargets.length * 18)}%` : "18%",
                      background: `linear-gradient(90deg, ${activeMessageColor}, rgba(255,255,255,0.92))`,
                    }}
                  />
                </div>
                <p className="mt-3 text-[11px] leading-5 text-[#5A5A5A]">
                  {activeMessage ? previewText(activeMessage.content, 90) : "The graph will come alive as the council starts sending messages."}
                </p>
              </div>

              <button
                onClick={() => setFocusedPersonaId((current) => (current === null ? positionedRoster[0]?.persona_id ?? null : null))}
                className="absolute left-3 top-3 flex items-center gap-1 border-[2px] border-black bg-[#E8FF8B] px-2 py-1 text-[10px] font-mono uppercase tracking-[0.25em] shadow-[2px_2px_0_0_#0A0A0A] transition hover:translate-x-px hover:translate-y-px hover:shadow-[1px_1px_0_0_#0A0A0A]"
              >
                <Crosshair className="h-3 w-3" />
                {effectiveFocusId ? "Lock Focus" : "Mesh Focus"}
              </button>

              <div className="absolute right-3 top-3 border-[2px] border-black bg-[#F0EDE6] px-3 py-2 text-right shadow-[2px_2px_0_0_#0A0A0A]">
                <div className="text-[10px] uppercase tracking-[0.28em] text-[#6B6B6B]">Forum Tempo</div>
                <div className="mt-1 font-mono text-xs text-black">
                  {isAutoplay ? "AUTOPLAY // LIVE" : "MANUAL // SCRUB"}
                </div>
              </div>

              <div className="absolute left-1/2 top-4 -translate-x-1/2 border-[2px] border-black bg-[#FFB86B] px-3 py-2 text-center shadow-[2px_2px_0_0_#0A0A0A]">
                <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.32em] text-black">
                  <UserRound className="h-3.5 w-3.5" />
                  You Brought The Question
                </div>
              </div>

              {positionedRoster.map((persona) => {
                const isFocused = effectiveFocusId === persona.persona_id;
                const isActiveSpeaker = activeMessage?.author_id === persona.persona_id;
                const influence = leaderboard.find((entry) => entry.persona.persona_id === persona.persona_id);
                return (
                  <button
                    key={persona.persona_id}
                    onClick={() =>
                      setFocusedPersonaId((current) => (current === persona.persona_id ? null : persona.persona_id))
                    }
                    className="absolute w-[108px] -translate-x-1/2 -translate-y-1/2 border px-2 py-2 text-left transition"
                    style={{
                      left: `${(persona.x / GRAPH_WIDTH) * 100}%`,
                      top: `${(persona.y / GRAPH_HEIGHT) * 100}%`,
                      background: isFocused
                        ? `linear-gradient(180deg, ${persona.color}50, rgba(255,255,255,0.96))`
                        : "linear-gradient(180deg, rgba(255,255,255,0.97), rgba(240,237,230,0.96))",
                      borderColor: isActiveSpeaker ? persona.color : `${persona.color}88`,
                      boxShadow: isActiveSpeaker
                        ? `4px 4px 0 0 #0A0A0A, 0 0 18px ${persona.color}45`
                        : isFocused
                        ? "4px 4px 0 0 #0A0A0A"
                        : "3px 3px 0 0 #0A0A0A",
                    }}
                  >
                    <div className="flex items-start gap-2">
                      <div
                        className="relative h-10 w-10 flex-shrink-0 overflow-hidden border-2 border-black bg-white"
                        style={{ imageRendering: "pixelated" }}
                      >
                        <img
                          src={`/pixelart/${persona.spriteFolder}/rotations/south.png`}
                          alt={persona.persona_name}
                          className="h-full w-full object-contain"
                          style={{ imageRendering: "pixelated" }}
                        />
                        {isActiveSpeaker && (
                          <div
                            className="pointer-events-none absolute inset-0"
                            style={{
                              background: `radial-gradient(circle, ${persona.color}55, transparent 68%)`,
                              animation: "bloom-blink 1.2s ease-in-out infinite",
                            }}
                          />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[11px] font-semibold uppercase tracking-[0.12em] text-black">
                          {persona.persona_name}
                        </div>
                        <div className="truncate font-mono text-[10px] text-[#6B6B6B]">
                          {persona.label}
                        </div>
                      </div>
                    </div>

                    <div className="mt-2 flex items-center justify-between font-mono text-[10px]">
                      <span className="text-[#6B6B6B]">Influence</span>
                      <span style={{ color: persona.color }}>{influence?.score ?? 0}</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden border border-black/15 bg-white">
                      <div
                        className="h-full"
                        style={{
                          width: `${Math.min(100, ((influence?.score ?? 0) / Math.max(leaderboard[0]?.score ?? 1, 1)) * 100)}%`,
                          background: `linear-gradient(90deg, ${persona.color}, rgba(255,255,255,0.92))`,
                        }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <aside className="min-w-0 flex flex-col gap-3">
            <section className="border-[3px] border-black bg-[#FFF9F1] p-3 shadow-[4px_4px_0_0_#0A0A0A]">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.3em] text-[#6B6B6B]">
                <Zap className="h-3.5 w-3.5" />
                Current Reply
              </div>

              {activeMessage ? (
                <>
                  <div className="mt-3 flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-black">
                        {activeMessage.role === "user" ? "You" : activeMessage.author_name}
                      </div>
                      <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-[#6B6B6B]">
                        {transmissionMode} · round {activeMessage.round_index}
                      </div>
                    </div>
                    {activeMessage.role === "persona" && (
                      <div
                        className="border px-2 py-1 text-[10px] font-mono uppercase tracking-[0.18em]"
                        style={{
                          borderColor: "#0A0A0A",
                          color: "#0A0A0A",
                          background: `${activeMessageColor}18`,
                        }}
                      >
                        live packet
                      </div>
                    )}
                  </div>

                  <p className="mt-3 text-sm leading-6 text-[#0A0A0A]">{activeMessage.content}</p>

                  <div className="mt-4 border-t-2 border-black/10 pt-3">
                    <div className="text-[11px] uppercase tracking-[0.24em] text-[#6B6B6B]">Routing</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {activeMessage.inferredTargets.map((targetId) => {
                        const target = positionedRoster.find((persona) => persona.persona_id === targetId);
                        if (!target) return null;
                        return (
                          <span
                            key={targetId}
                            className="inline-flex items-center gap-1 border px-2 py-1 text-[10px] font-mono uppercase tracking-[0.18em]"
                            style={{
                              borderColor: `${target.color}66`,
                              color: target.color,
                              background: `${target.color}15`,
                            }}
                          >
                            <PhilosopherIcon philosopherId={targetId} className="h-3 w-3" />
                            {target.persona_name}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                </>
              ) : (
                <p className="mt-3 text-sm text-[#6B6B6B]">
                  No persona message has been selected yet. As soon as transmissions appear, the inspector will bind to the latest packet.
                </p>
              )}
            </section>

            <section className="border-[3px] border-black bg-[#FFFFFF] p-3 shadow-[4px_4px_0_0_#0A0A0A]">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-[#6B6B6B]">
                <Target className="h-3.5 w-3.5" />
                Speaker Focus
              </div>
              {selectedPersona ? (
                <>
                  <div className="mt-3 flex items-center gap-3">
                    <div
                      className="flex h-12 w-12 items-center justify-center border-2 border-black"
                      style={{
                        background: `${selectedPersona.color}18`,
                      }}
                    >
                      <PhilosopherIcon philosopherId={selectedPersona.persona_id} className="h-6 w-6" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-black">{selectedPersona.persona_name}</div>
                      <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-[#6B6B6B]">
                        {selectedPersona.label} · {Math.round(selectedPersona.confidence * 100)}% confidence
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 overflow-hidden border-2 border-black bg-[#F8F4ED] p-2">
                    <svg viewBox="0 0 220 66" className="h-20 w-full">
                      <path
                        d={sparklinePath(selectedTrajectory)}
                        fill="none"
                        stroke={selectedPersona.color}
                        strokeWidth="2.6"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <div className="mt-1 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.18em] text-[#6B6B6B]">
                      <span>R0</span>
                      <span>stance trace</span>
                      <span>R{roundGoal}</span>
                    </div>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-[#0A0A0A]">{selectedPersona.rationale}</p>
                </>
              ) : (
                <p className="mt-3 text-sm text-[#6B6B6B]">Select a sprite node to lock the graph onto its influence lane.</p>
              )}
            </section>

            <section className="border-[3px] border-black bg-[#FCFBF6] p-3 shadow-[4px_4px_0_0_#0A0A0A]">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-[#6B6B6B]">
                <Activity className="h-3.5 w-3.5" />
                Influence Ladder
              </div>
              <div className="mt-3 space-y-2">
                {leaderboard.map((entry, index) => (
                  <button
                    key={entry.persona.persona_id}
                    onClick={() => setFocusedPersonaId(entry.persona.persona_id)}
                    className="w-full border-2 border-black bg-white px-2 py-2 text-left shadow-[2px_2px_0_0_#0A0A0A] transition hover:translate-x-px hover:translate-y-px hover:shadow-[1px_1px_0_0_#0A0A0A]"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-[#6B6B6B]">#{index + 1}</span>
                      <div
                        className="h-6 w-6 border border-black"
                        style={{
                          background: `${entry.persona.color}18`,
                        }}
                      >
                        <PhilosopherIcon philosopherId={entry.persona.persona_id} className="h-full w-full p-1" />
                      </div>
                      <span className="flex-1 truncate text-xs font-semibold text-black">
                        {entry.persona.persona_name}
                      </span>
                      <span className="font-mono text-[10px]" style={{ color: entry.persona.color }}>
                        {entry.score}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden border border-black/15 bg-[#F0EDE6]">
                      <div
                        className="h-full"
                        style={{
                          width: `${Math.min(100, (entry.score / Math.max(leaderboard[0]?.score ?? 1, 1)) * 100)}%`,
                          background: `linear-gradient(90deg, ${entry.persona.color}, rgba(255,255,255,0.9))`,
                        }}
                      />
                    </div>
                  </button>
                ))}
              </div>
            </section>
          </aside>

          <section className="min-w-0 xl:col-span-2 border-[3px] border-black bg-[#FFFDF9] p-3 shadow-[4px_4px_0_0_#0A0A0A]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-[11px] uppercase tracking-[0.32em] text-[#6B6B6B]">
                Reply Timeline
              </div>
              <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#6B6B6B]">
                {interactiveMessages.length === 0
                  ? "Awaiting transmissions"
                  : `message ${activeMessageIndex + 1} / ${interactiveMessages.length}`}
              </div>
            </div>

            <input
              type="range"
              min={0}
              max={Math.max(interactiveMessages.length - 1, 0)}
              step={1}
              value={activeMessageIndex}
              onChange={(event) => {
                setIsAutoplay(false);
                setActiveMessageIndex(Number(event.target.value));
              }}
              disabled={interactiveMessages.length === 0}
              className="mt-3 w-full accent-black"
            />

            <div className="mt-3 flex min-w-0 gap-2 overflow-x-auto pb-1">
              {interactiveMessages.map((message, index) => {
                const color =
                  message.role === "user"
                    ? "#FFB347"
                    : positionedRoster.find((persona) => persona.persona_id === message.author_id)?.color ?? "#4FE5FF";
                const active = index === activeMessageIndex;
                return (
                  <button
                    key={message.id}
                    onClick={() => {
                      setIsAutoplay(false);
                      setActiveMessageIndex(index);
                    }}
                    className="min-w-[170px] flex-shrink-0 border-2 border-black px-3 py-2 text-left transition"
                    style={{
                      background: active ? `linear-gradient(135deg, ${color}22, #ffffff)` : "#F8F4ED",
                      boxShadow: active ? "3px 3px 0 0 #0A0A0A" : "2px 2px 0 0 #0A0A0A",
                    }}
                  >
                    <div className="flex items-center justify-between gap-2 font-mono text-[10px] uppercase tracking-[0.18em]">
                      <span style={{ color }}>{message.role === "user" ? "uplink" : message.author_name}</span>
                      <span className="text-[#6B6B6B]">r{message.round_index}</span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-[#0A0A0A]">{previewText(message.content, 72)}</p>
                  </button>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
