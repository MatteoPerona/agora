import { ReactNode, CSSProperties } from "react";

interface BrutalistCardProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  variant?: "default" | "accent" | "secondary" | "green";
  hoverable?: boolean;
  onClick?: () => void;
  onMouseEnter?: (e: React.MouseEvent<HTMLDivElement>) => void;
  onMouseLeave?: (e: React.MouseEvent<HTMLDivElement>) => void;
}

export function BrutalistCard({ 
  children, 
  className = "", 
  style,
  variant = "default",
  hoverable = false,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: BrutalistCardProps) {
  const variants = {
    default: "bg-white border-[3px] border-black shadow-[4px_4px_0_0_#0A0A0A]",
    accent: "bg-[#FF6B9D] border-[3px] border-black shadow-[4px_4px_0_0_#0A0A0A]",
    secondary: "bg-[#E8FF8B] border-[3px] border-black shadow-[4px_4px_0_0_#0A0A0A]",
    green: "bg-[#8BFFA7] border-[3px] border-black shadow-[4px_4px_0_0_#0A0A0A]",
  };

  const hoverClass = hoverable 
    ? "transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0_0_#0A0A0A] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none" 
    : "";

  return (
    <div
      className={`${variants[variant]} ${hoverClass} ${className}`}
      style={style}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </div>
  );
}
