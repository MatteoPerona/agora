import { useEffect, useRef, useState } from "react";

type Direction = "south" | "east" | "west" | "south-east" | "south-west";

const PHILOSOPHER_QUIPS: Record<string, string[]> = {
  aristotle: ["Logic.", "Virtue!", "The mean.", "Form > matter.", "Think harder."],
  Diogenes: ["Go away.", "I need nothing.", "Your house is too big.", "Barrel life.", "Touch grass."],
  epicurus: ["Pleasure = good.", "Chill out.", "Friends first.", "Less is more.", "Avoid pain."],
  marcus: ["Memento mori.", "Do the work.", "It is what it is.", "Amor fati.", "Discipline."],
  seneca: ["Time flies.", "Hurry slowly.", "Less talk.", "Live now.", "Letters > meetings."],
  socrates: ["I know nothing.", "Question it.", "Examine this.", "But why though?", "Define your terms."],
};

const GENERIC_QUIPS = [
  "Hmm.",
  "Interesting.",
  "Ponder this.",
  "...",
  "What is truth?",
  "Be good.",
  "Think.",
  "Truly?",
  "Indeed.",
  "Curious.",
];

function getQuip(character: string): string {
  const pool = PHILOSOPHER_QUIPS[character] ?? GENERIC_QUIPS;
  return pool[Math.floor(Math.random() * pool.length)];
}

function PixelSpeechBubble({ text }: { text: string }) {
  return (
    <div
      className="absolute select-none"
      style={{ bottom: "100%", left: "50%", transform: "translateX(-50%)", marginBottom: 4, zIndex: 10 }}
    >
      <div
        style={{
          border: "2px solid black",
          background: "white",
          boxShadow: "2px 2px 0 0 #000",
          padding: "3px 6px",
          whiteSpace: "nowrap",
          fontFamily: "monospace",
          fontSize: "10px",
          letterSpacing: "0.02em",
          lineHeight: 1.3,
        }}
      >
        {text}
      </div>
    </div>
  );
}

interface DesktopPetProps {
  character: string;
  initialX: number; // 0–100 as % of window width
  initialDelay?: number; // ms before starting to move
  scale?: number; // pixel scale multiplier (default 3)
  bottomOffset?: number; // px from bottom
}

export function DesktopPet({
  character,
  initialX,
  initialDelay = 0,
  scale = 3,
  bottomOffset = -30,
}: DesktopPetProps) {
  const spriteSize = 48 * scale;

  const [x, setX] = useState(() => (initialX / 100) * window.innerWidth);
  const [direction, setDirection] = useState<Direction>("south");
  const [active, setActive] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [quip, setQuip] = useState("");

  const targetXRef = useRef<number>((initialX / 100) * window.innerWidth);
  const phaseRef = useRef<"walking" | "idle">("idle");
  const xRef = useRef<number>((initialX / 100) * window.innerWidth);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pickNewTarget = () => {
    const margin = spriteSize;
    const maxX = window.innerWidth - margin;
    const minX = margin;
    let newTarget = minX + Math.random() * (maxX - minX);
    newTarget = Math.max(minX, Math.min(maxX, newTarget));
    targetXRef.current = newTarget;
    phaseRef.current = "walking";
  };

  const scheduleIdle = () => {
    phaseRef.current = "idle";
    setDirection("south");
    const idleTime = 800 + Math.random() * 2200;
    idleTimerRef.current = setTimeout(() => {
      pickNewTarget();
    }, idleTime);
  };

  useEffect(() => {
    const startDelay = setTimeout(() => {
      setActive(true);
      pickNewTarget();

      const SPEED = 1.2;
      const FPS = 30;

      tickRef.current = setInterval(() => {
        if (phaseRef.current !== "walking") return;

        const target = targetXRef.current;
        const current = xRef.current;
        const diff = target - current;

        if (Math.abs(diff) < SPEED + 1) {
          xRef.current = target;
          setX(target);
          scheduleIdle();
          return;
        }

        const step = diff > 0 ? SPEED : -SPEED;
        const next = current + step;
        xRef.current = next;
        setX(next);

        if (diff > 0) {
          setDirection("east");
        } else {
          setDirection("west");
        }
      }, 1000 / FPS);
    }, initialDelay);

    return () => {
      clearTimeout(startDelay);
      if (tickRef.current) clearInterval(tickRef.current);
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!active) return null;

  const spritePath = `/pixelart/${character}/rotations/${direction}.png`;

  return (
    <div
      className="fixed select-none z-[2]"
      style={{
        left: x - spriteSize / 2,
        bottom: bottomOffset,
        width: spriteSize,
        height: spriteSize,
        pointerEvents: "none",
      }}
    >
      {/* hover target — pointer-events enabled only on the sprite */}
      <div
        className="relative w-full h-full"
        style={{ pointerEvents: "auto", cursor: "pointer" }}
        onMouseEnter={() => { setQuip(getQuip(character)); setHovered(true); }}
        onMouseLeave={() => setHovered(false)}
      >
        {hovered && <PixelSpeechBubble text={quip} />}
        <img
          src={spritePath}
          alt={character}
          style={{
            width: spriteSize,
            height: spriteSize,
            imageRendering: "pixelated",
          }}
        />
      </div>
    </div>
  );
}
