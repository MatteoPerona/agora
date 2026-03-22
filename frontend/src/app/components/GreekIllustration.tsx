interface GreekIllustrationProps {
  type: "column" | "bust" | "amphora" | "scroll" | "laurel" | "pediment";
  className?: string;
}

export function GreekIllustration({ type, className = "" }: GreekIllustrationProps) {
  const illustrations = {
    column: (
      <svg viewBox="0 0 80 120" className={className} fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="15" y="10" width="50" height="8" />
        <rect x="20" y="18" width="40" height="84" />
        <rect x="15" y="102" width="50" height="8" />
        <line x1="25" y1="18" x2="25" y2="102" />
        <line x1="35" y1="18" x2="35" y2="102" />
        <line x1="45" y1="18" x2="45" y2="102" />
        <line x1="55" y1="18" x2="55" y2="102" />
      </svg>
    ),
    bust: (
      <svg viewBox="0 0 80 100" className={className} fill="none" stroke="currentColor" strokeWidth="2">
        <ellipse cx="40" cy="35" rx="18" ry="20" />
        <path d="M 22 50 Q 22 65 15 80 L 65 80 Q 58 65 58 50 Z" />
        <circle cx="33" cy="32" r="2" fill="currentColor" />
        <circle cx="47" cy="32" r="2" fill="currentColor" />
        <path d="M 33 42 Q 40 45 47 42" strokeLinecap="round" />
        <path d="M 30 26 Q 35 24 40 26" strokeLinecap="round" />
        <path d="M 40 26 Q 45 24 50 26" strokeLinecap="round" />
      </svg>
    ),
    amphora: (
      <svg viewBox="0 0 60 100" className={className} fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M 30 10 L 25 15 L 20 25 Q 18 40 20 55 Q 22 70 25 80 L 30 90 L 35 80 Q 38 70 40 55 Q 42 40 40 25 L 35 15 Z" />
        <ellipse cx="30" cy="10" rx="5" ry="3" />
        <line x1="20" y1="15" x2="15" y2="20" />
        <line x1="40" y1="15" x2="45" y2="20" />
        <path d="M 20 40 Q 30 38 40 40" />
        <path d="M 22 60 Q 30 58 38 60" />
      </svg>
    ),
    scroll: (
      <svg viewBox="0 0 100 60" className={className} fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="5" y="15" width="8" height="30" rx="4" />
        <rect x="87" y="15" width="8" height="30" rx="4" />
        <path d="M 13 20 L 87 20" />
        <path d="M 13 40 L 87 40" />
        <path d="M 20 28 L 75 28" strokeDasharray="2 2" />
        <path d="M 20 32 L 70 32" strokeDasharray="2 2" />
      </svg>
    ),
    laurel: (
      <svg viewBox="0 0 100 100" className={className} fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M 20 80 Q 20 50 30 30 Q 40 15 50 10 Q 60 15 70 30 Q 80 50 80 80" strokeLinecap="round" />
        <ellipse cx="25" cy="70" rx="4" ry="6" />
        <ellipse cx="30" cy="55" rx="4" ry="6" transform="rotate(-20 30 55)" />
        <ellipse cx="35" cy="40" rx="4" ry="6" transform="rotate(-30 35 40)" />
        <ellipse cx="42" cy="28" rx="4" ry="6" transform="rotate(-40 42 28)" />
        <ellipse cx="75" cy="70" rx="4" ry="6" />
        <ellipse cx="70" cy="55" rx="4" ry="6" transform="rotate(20 70 55)" />
        <ellipse cx="65" cy="40" rx="4" ry="6" transform="rotate(30 65 40)" />
        <ellipse cx="58" cy="28" rx="4" ry="6" transform="rotate(40 58 28)" />
      </svg>
    ),
    pediment: (
      <svg viewBox="0 0 100 50" className={className} fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M 10 10 L 50 5 L 90 10" />
        <path d="M 10 40 L 50 35 L 90 40" />
        <path d="M 10 10 L 10 40" />
        <path d="M 90 10 L 90 40" />
        <path d="M 50 5 L 50 35" />
      </svg>
    ),
  };

  return illustrations[type];
}