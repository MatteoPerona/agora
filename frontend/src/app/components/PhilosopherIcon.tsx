import { Icon } from '@iconify/react';

interface PhilosopherIconProps {
  philosopherId?: string;
  type?: string;
  className?: string;
}

export function PhilosopherIcon({ philosopherId, type, className = "w-12 h-12" }: PhilosopherIconProps) {
  // Special icons for verdict page
  if (type === "laurel") {
    return <Icon icon="fluent:wreath-20-regular" className={className} />;
  }

  if (type === "scroll") {
    return <Icon icon="lucide:scroll-text" className={className} />;
  }

  if (!philosopherId) {
    return <Icon icon="lucide:user" className={className} />;
  }

  const iconMap: Record<string, string> = {
    // Using Iconify's vast collection - Streamline-style and other premium icons
    socrates: "icon-park-outline:thinking-problem", // Questioning/thinking face
    epicurus: "mdi:food-apple-outline", // Pleasure/simple pleasures
    diogenes: "game-icons:barrel", // His famous barrel
    aristotle: "ph:scroll", // Scholar/knowledge
    seneca: "material-symbols:balance", // Stoic balance
    marcus: "lucide:crown", // Emperor's crown
  };

  return <Icon icon={iconMap[philosopherId] || "lucide:user"} className={className} />;
}