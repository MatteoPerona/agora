import { useNavigate, useLocation, useParams } from "react-router";
import { useEffect, useRef, useState } from "react";
import { BrutalistButton } from "../components/BrutalistButton";
import { BrutalistCard } from "../components/BrutalistCard";
import { PhilosopherIcon } from "../components/PhilosopherIcon";
import { ArrowLeft, ThumbsUp, ThumbsDown, Minus, Loader2, RotateCcw, Home } from "lucide-react";
import { getSession, personaColor, stanceLabel } from "../lib/api";
import type { SessionSnapshot, TrajectorySeries } from "../lib/types";
import { PHILOSOPHERS } from "../data/philosophers";

const PHILOSOPHER_COLORS: Record<string, string> = Object.fromEntries(
  PHILOSOPHERS.map((p) => [p.id, p.color])
);
const PHILOSOPHER_SUBTITLE: Record<string, string> = Object.fromEntries(
  PHILOSOPHERS.map((p) => [p.id, p.stance])
);

// ── Stance evolution sparkline ──────────────────────────────────────────────
function EvolutionChart({ series, color }: { series: TrajectorySeries; color: string }) {
  const W = 200;
  const H = 52;
  const PAD = 8;
  const pts = series.points;
  if (pts.length < 2) return null;

  const maxRound = Math.max(...pts.map((p) => p.round_index), 1);
  const xOf = (r: number) => PAD + (r / maxRound) * (W - PAD * 2);
  const yOf = (s: number) => PAD + ((1 - s) / 2) * (H - PAD * 2);

  const polyline = pts.map((p) => `${xOf(p.round_index)},${yOf(p.stance)}`).join(" ");
  const first = pts[0];
  const last = pts[pts.length - 1];
  const delta = last.stance - first.stance;

  return (
    <div className="flex-shrink-0">
      <p className="text-[10px] text-muted-foreground mb-1 text-right">
        {delta > 0.05 ? "moved toward agree" : delta < -0.05 ? "moved toward disagree" : "held position"}
      </p>
      <svg width={W} height={H}>
        {/* background regions */}
        <rect x={PAD} y={PAD} width={W - PAD * 2} height={(H - PAD * 2) / 2} fill="#A7F3D020" />
        <rect x={PAD} y={H / 2} width={W - PAD * 2} height={(H - PAD * 2) / 2} fill="#FCA5A520" />
        {/* zero line */}
        <line x1={PAD} y1={H / 2} x2={W - PAD} y2={H / 2} stroke="#C0C0C0" strokeWidth={1} strokeDasharray="4 3" />
        {/* trend line */}
        <polyline
          points={polyline}
          fill="none"
          stroke={color}
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* dots */}
        {pts.map((p, i) => (
          <circle key={i} cx={xOf(p.round_index)} cy={yOf(p.stance)} r={3.5} fill={color} stroke="white" strokeWidth={1.5} />
        ))}
        {/* start / end labels */}
        <text x={xOf(first.round_index)} y={H - 1} fontSize={8} fill="#888" textAnchor="middle">R{first.round_index}</text>
        <text x={xOf(last.round_index)} y={H - 1} fontSize={8} fill="#888" textAnchor="middle">R{last.round_index}</text>
      </svg>
    </div>
  );
}

// ── Sentiment badge ─────────────────────────────────────────────────────────
function SentimentBadge({ label, confidence }: { label: "for" | "against" | "undecided"; confidence: number }) {
  const cfg = {
    for:       { bg: "#A7F3D0", icon: <ThumbsUp  className="w-3.5 h-3.5" />, text: "agree"    },
    against:   { bg: "#FCA5A5", icon: <ThumbsDown className="w-3.5 h-3.5" />, text: "disagree" },
    undecided: { bg: "#E0E0E0", icon: <Minus      className="w-3.5 h-3.5" />, text: "neutral"  },
  }[label];
  return (
    <div
      className="flex items-center gap-1.5 px-2.5 py-1 border-2 border-black text-xs font-semibold flex-shrink-0"
      style={{ backgroundColor: cfg.bg }}
    >
      {cfg.icon}
      <span>{cfg.text}</span>
      <span className="opacity-60">{Math.round(confidence * 100)}%</span>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────
export function Verdict() {
  const location = useLocation();
  const navigate = useNavigate();
  const { debateId: sessionId } = useParams<{ debateId: string }>();

  const question: string = location.state?.question || sessionStorage.getItem("agora-question") || "";
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(location.state?.snapshot ?? null);
  const [loading, setLoading] = useState(!location.state?.snapshot);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const hasRedirected = useRef(false);

  useEffect(() => {
    if (snapshot) return;
    if (!sessionId) {
      if (!hasRedirected.current) { hasRedirected.current = true; navigate("/", { replace: true }); }
      return;
    }
    setLoading(true);
    getSession(sessionId)
      .then(setSnapshot)
      .catch((e) => setFetchError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center gap-3">
        <Loader2 className="w-6 h-6 animate-spin" />
        <span>Loading report...</span>
      </div>
    );
  }

  if (fetchError || !snapshot) {
    return (
      <div className="min-h-screen p-8 flex flex-col items-center justify-center gap-4">
        <BrutalistCard className="p-6 max-w-md text-center">
          <p className="font-semibold mb-2">Could not load report</p>
          <p className="text-sm text-muted-foreground mb-4">{fetchError}</p>
          <BrutalistButton variant="primary" onClick={() => navigate("/")}>Return Home</BrutalistButton>
        </BrutalistCard>
      </div>
    );
  }

  const brief = snapshot.brief;
  const roster = snapshot.roster;
  const trajMap = new Map<string, TrajectorySeries>(snapshot.trajectories.map((t) => [t.persona_id, t]));

  // Aggregate sentiment counts
  const agreeCt    = roster.filter((r) => r.label === "for").length;
  const disagreeCt = roster.filter((r) => r.label === "against").length;
  const neutralCt  = roster.filter((r) => r.label === "undecided").length;
  const total      = roster.length || 1;
  const pct        = (n: number) => Math.round((n / total) * 100);

  return (
    <div className="min-h-screen p-4 md:p-8 pb-16">
      <div className="max-w-4xl mx-auto">

        {/* Back */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 mb-8 hover:translate-x-[-2px] transition-transform text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to debate
        </button>

        {/* Hero header */}
        <BrutalistCard variant="secondary" className="p-6 mb-8">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Council Report</p>
              <h1 className="text-3xl md:text-4xl font-black mb-2 leading-tight">
                {brief?.headline ?? "The debate has concluded"}
              </h1>
              <p className="text-xs text-muted-foreground mb-1">
                Personas: {roster.map((r) => r.persona_name).join(", ")}
              </p>
              <p className="text-muted-foreground text-sm">"{question || snapshot.decision}"</p>
            </div>
            <div className="flex gap-3 text-center flex-shrink-0">
              {[
                { label: "Agree",    count: agreeCt,    bg: "#A7F3D0" },
                { label: "Disagree", count: disagreeCt, bg: "#FCA5A5" },
                { label: "Neutral",  count: neutralCt,  bg: "#E0E0E0" },
              ].map(({ label, count, bg }) => (
                <div key={label} className="border-2 border-black px-3 py-2" style={{ backgroundColor: bg }}>
                  <p className="text-2xl font-black">{pct(count)}%</p>
                  <p className="text-xs">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </BrutalistCard>

        {/* TLDR summary */}
        {brief?.landscape_summary && (
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold bg-black text-white px-2 py-1 tracking-wider">SUMMARY</span>
            </div>
            <BrutalistCard className="p-5 bg-[#F0EDE6]">
              <p className="leading-relaxed">{brief.landscape_summary}</p>
            </BrutalistCard>
          </div>
        )}

        {/* Agent opinions */}
        <div className="mb-8">
          <h2 className="text-xl font-black mb-4">How Each Voice Landed</h2>
          <div className="space-y-4">
            {roster.map((r, idx) => {
              const color = PHILOSOPHER_COLORS[r.persona_id] ?? personaColor(idx);
              const subtitle = PHILOSOPHER_SUBTITLE[r.persona_id];
              const traj = trajMap.get(r.persona_id);
              const label = stanceLabel(r.stance);

              return (
                <BrutalistCard key={r.persona_id} className="p-5">
                  <div className="flex gap-4 items-start">
                    {/* Avatar */}
                    <div
                      className="w-12 h-12 flex-shrink-0 flex items-center justify-center border-2 border-black"
                      style={{ backgroundColor: color }}
                    >
                      <PhilosopherIcon philosopherId={r.persona_id} className="w-6 h-6" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3 mb-2 flex-wrap">
                        <div>
                          <h3 className="font-bold text-base leading-tight">{r.persona_name}</h3>
                          {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
                        </div>
                        <SentimentBadge label={label} confidence={r.confidence} />
                      </div>

                      {r.rationale && (
                        <p className="text-sm text-muted-foreground leading-relaxed mb-3">{r.rationale}</p>
                      )}

                      {/* Evolution chart */}
                      {traj && traj.points.length >= 2 && (
                        <div className="border-t border-black/10 pt-3">
                          <p className="text-xs font-semibold mb-2 text-muted-foreground uppercase tracking-wide">Opinion over time</p>
                          <EvolutionChart series={traj} color={color} />
                        </div>
                      )}
                    </div>
                  </div>
                </BrutalistCard>
              );
            })}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => navigate("/summon", { state: { question } })}
            className="flex items-center justify-center gap-2 border-[3px] border-black bg-black text-white px-6 py-2.5 shadow-[3px_3px_0_0_#0A0A0A] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[2px_2px_0_0_#0A0A0A] transition-all text-sm font-semibold"
          >
            <RotateCcw className="w-4 h-4" />
            Rerun Simulation
          </button>
          <button
            onClick={() => navigate("/")}
            className="flex items-center justify-center gap-2 border-[3px] border-black bg-white px-6 py-2.5 shadow-[3px_3px_0_0_#0A0A0A] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[2px_2px_0_0_#0A0A0A] transition-all text-sm font-semibold"
          >
            <Home className="w-4 h-4" />
            Return Home
          </button>
        </div>

      </div>
    </div>
  );
}
