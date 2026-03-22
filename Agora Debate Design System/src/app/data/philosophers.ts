export interface Philosopher {
  id: string;
  name: string;
  era: string;
  stance: string;
  description: string;
  color: string;
  emoji: string;
}

export const PHILOSOPHERS: Philosopher[] = [
  {
    id: "socrates",
    name: "Socrates",
    era: "470–399 BCE",
    stance: "The Questioner",
    description: "Questions everything to uncover truth. Uses dialectic method to examine assumptions and challenge conventional wisdom.",
    color: "#FF6B9D",
    emoji: "🤔",
  },
  {
    id: "epicurus",
    name: "Epicurus",
    era: "341–270 BCE",
    stance: "The Hedonist",
    description: "Seeks pleasure and happiness through simple living. Values friendship, freedom, and peace of mind above all else.",
    color: "#E8FF8B",
    emoji: "🍷",
  },
  {
    id: "diogenes",
    name: "Diogenes",
    era: "412–323 BCE",
    stance: "The Cynic",
    description: "Rejects social conventions and material possessions. Lives according to nature and speaks uncomfortable truths.",
    color: "#6B9DFF",
    emoji: "🏺",
  },
  {
    id: "aristotle",
    name: "Aristotle",
    era: "384–322 BCE",
    stance: "The Logician",
    description: "Analyzes systematically through reason and observation. Seeks the golden mean between extremes in all things.",
    color: "#FF8B6B",
    emoji: "📜",
  },
  {
    id: "seneca",
    name: "Seneca",
    era: "4 BCE–65 CE",
    stance: "The Stoic",
    description: "Focuses on what's in your control. Accepts fate with equanimity and prepares for both fortune and hardship.",
    color: "#8B6BFF",
    emoji: "⚖️",
  },
  {
    id: "marcus",
    name: "Marcus Aurelius",
    era: "121–180 CE",
    stance: "The Emperor",
    description: "Balances duty with wisdom. Remembers mortality and acts with justice, courage, and moderation.",
    color: "#FFB86B",
    emoji: "👑",
  },
];

export interface DebateMessage {
  id: string;
  philosopherId: string;
  message: string;
  timestamp: number;
  sentiment: "agree" | "disagree" | "neutral";
  replyTo?: string;
}

export interface Debate {
  id: string;
  question: string;
  participants: string[];
  messages: DebateMessage[];
  status: "active" | "concluded";
  verdict?: string;
}