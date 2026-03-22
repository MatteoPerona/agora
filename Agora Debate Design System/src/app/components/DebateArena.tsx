import { useState, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { Message, PersonaStance } from "../lib/types";

const SPRITE_FOLDER: Record<string, string> = {
  socrates: "socrates",
  epicurus: "epicurus",
  diogenes: "Diogenes",
  aristotle: "aristotle",
  seneca: "seneca",
  marcus: "marcus",
};
const FALLBACK_SPRITES = ["1", "2", "3"];

function getSpriteFolder(personaId: string, fallbackIndex: number): string {
  return SPRITE_FOLDER[personaId] ?? FALLBACK_SPRITES[fallbackIndex % 3];
}

const SPRITE_SIZE = 96;
const MAX_BUBBLE_WIDTH = 200;
const MIN_BUBBLE_WIDTH = 80;
const CHARS_PER_TICK = 2;
const TICK_MS = 22;
const BUBBLE_LINGER_MS = 10_000;
const ARENA_HEIGHT = 420;

// Ground level waypoints: [xPct, bottomPx]
// Derived from the red line in the background image.
// Left section is flat at ~33px; the terrain steps down at ~83% x to ~22px on the right.
const GROUND_WAYPOINTS: [number, number][] = [
  [0,   13],
  [80,  13],
  [84,  24],
  [100, 24],
];

function getGroundBottom(xPct: number): number {
  for (let i = 0; i < GROUND_WAYPOINTS.length - 1; i++) {
    const [x0, y0] = GROUND_WAYPOINTS[i];
    const [x1, y1] = GROUND_WAYPOINTS[i + 1];
    if (xPct >= x0 && xPct <= x1) {
      const t = (xPct - x0) / (x1 - x0);
      return Math.round(y0 + t * (y1 - y0));
    }
  }
  return GROUND_WAYPOINTS[GROUND_WAYPOINTS.length - 1][1];
}

// Per-persona bubble: what's currently displayed vs the full text
type BubbleState = { displayedText: string; fullText: string; messageId: string };

interface DebateArenaProps {
  roster: PersonaStance[];
  latestMessage: Message | null;
}

export function DebateArena({ roster, latestMessage }: DebateArenaProps) {
  const [bg, setBg] = useState<"day" | "night">("day");
  const [containerWidth, setContainerWidth] = useState(900);
  const containerRef = useRef<HTMLDivElement>(null);
  // Map of personaId → bubble state
  const [bubbles, setBubbles] = useState<Record<string, BubbleState>>({});
  // Which persona's bubble is actively typewriting right now
  const [typingPersonaId, setTypingPersonaId] = useState<string | null>(null);

  // Measure container width for dynamic bubble sizing
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setContainerWidth(entry.contentRect.width);
    });
    ro.observe(el);
    setContainerWidth(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  const n = roster.length || 1;

  // Bubble width = 85% of each sprite's horizontal slot, clamped
  const bubbleWidth = Math.round(
    Math.min(MAX_BUBBLE_WIDTH, Math.max(MIN_BUBBLE_WIDTH, (containerWidth / n) * 0.85))
  );

  // On mount, record the current message ID as "already seen" so we don't replay it
  const initialMessageIdRef = useRef<string | undefined>(latestMessage?.id);

  // One typewriter tick interval (only one speaks at a time)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const charIndexRef = useRef(0);

  // Per-persona linger timers
  const hideTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    // Skip the message that was already visible when the component mounted
    if (!latestMessage || latestMessage.role !== "persona") return;
    if (latestMessage.id === initialMessageIdRef.current) return;

    const { author_id, content, id } = latestMessage;

    // Clear any existing typewriter
    if (tickRef.current) clearInterval(tickRef.current);

    // Clear this persona's existing hide timer
    if (hideTimersRef.current[author_id]) {
      clearTimeout(hideTimersRef.current[author_id]);
      delete hideTimersRef.current[author_id];
    }

    // Start the persona's bubble empty and begin typing
    setBubbles((prev) => ({
      ...prev,
      [author_id]: { displayedText: "", fullText: content, messageId: id },
    }));
    setTypingPersonaId(author_id);
    charIndexRef.current = 0;

    tickRef.current = setInterval(() => {
      charIndexRef.current += CHARS_PER_TICK;
      if (charIndexRef.current >= content.length) {
        // Typing done — show full text and start linger timer
        setBubbles((prev) => ({
          ...prev,
          [author_id]: { displayedText: content, fullText: content, messageId: id },
        }));
        setTypingPersonaId(null);
        clearInterval(tickRef.current!);
        tickRef.current = null;

        hideTimersRef.current[author_id] = setTimeout(() => {
          setBubbles((prev) => {
            const next = { ...prev };
            delete next[author_id];
            return next;
          });
          delete hideTimersRef.current[author_id];
        }, BUBBLE_LINGER_MS);
      } else {
        setBubbles((prev) => ({
          ...prev,
          [author_id]: {
            displayedText: content.slice(0, charIndexRef.current),
            fullText: content,
            messageId: id,
          },
        }));
      }
    }, TICK_MS);

    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
    };
  }, [latestMessage?.id]);

  // Cleanup all timers on unmount
  useEffect(() => {
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
      Object.values(hideTimersRef.current).forEach(clearTimeout);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full border-4 border-black select-none"
      style={{ height: ARENA_HEIGHT }}
    >
      {/* Background clipped separately so bubbles aren't cut off */}
      <div className="absolute inset-0 overflow-hidden">
        <img
          src={`/pixelart/${bg}.png`}
          alt=""
          className="w-full h-full object-cover"
          style={{ imageRendering: "pixelated" }}
        />
      </div>

      {/* Day / Night toggle */}
      <button
        onClick={() => setBg((b) => (b === "day" ? "night" : "day"))}
        className="absolute top-2 right-2 z-20 border-2 border-black bg-white px-2 py-1 text-xs font-mono shadow-[2px_2px_0_0_#000] hover:translate-x-px hover:translate-y-px hover:shadow-none transition-all"
      >
        {bg === "day" ? "Night" : "Day"}
      </button>

      {/* Sprites + per-persona speech bubbles */}
      {roster.map((persona, i) => {
        const folder = getSpriteFolder(persona.persona_id, i);
        const isTyping = persona.persona_id === typingPersonaId;
        const leftPct = ((i + 0.5) / n) * 100;
        const groundBottom = getGroundBottom(leftPct);
        const bubble = bubbles[persona.persona_id];
        const bubbleBottom = groundBottom + SPRITE_SIZE + 8;

        return (
          <div key={persona.persona_id}>
            {/* Speech bubble — centered via calc() to avoid framer motion transform conflict */}
            <AnimatePresence>
              {bubble && (
                <motion.div
                  key={bubble.messageId}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="absolute bg-white border-2 border-black shadow-[2px_2px_0_0_#000] px-2 py-2 z-30"
                  style={{
                    left: `calc(${leftPct}% - ${bubbleWidth / 2}px)`,
                    bottom: bubbleBottom,
                    width: bubbleWidth,
                    fontFamily: "monospace",
                    fontSize: 9,
                    lineHeight: 1.55,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {bubble.displayedText.slice(0, 120)}{bubble.displayedText.length > 120 ? "…" : ""}
                  {isTyping && (
                    <span style={{ animation: "blink 0.7s step-end infinite" }}>▌</span>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Sprite */}
            <div
              className="absolute flex flex-col items-center"
              style={{
                left: `calc(${leftPct}% - ${SPRITE_SIZE / 2}px)`,
                bottom: groundBottom,
                width: SPRITE_SIZE,
                zIndex: isTyping ? 10 : 5,
              }}
            >
              <motion.img
                key={isTyping ? latestMessage?.id : persona.persona_id}
                src={`/pixelart/${folder}/rotations/south.png`}
                alt={persona.persona_name}
                animate={isTyping ? { y: [0, -6, 0, -3, 0] } : { y: 0 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                style={{
                  width: SPRITE_SIZE,
                  height: SPRITE_SIZE,
                  imageRendering: "pixelated",
                }}
              />
              <div
                className="mt-1 border border-black bg-white px-1 leading-tight"
                style={{ fontFamily: "monospace", fontSize: 8, whiteSpace: "nowrap" }}
              >
                {persona.persona_name.split(" ")[0]}
              </div>
            </div>
          </div>
        );
      })}

      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
}
