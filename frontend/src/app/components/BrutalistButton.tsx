import { ReactNode } from "react";

interface BrutalistButtonProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "accent" | "green" | "terracotta" | "grey";
  size?: "sm" | "md" | "lg";
  className?: string;
  type?: "button" | "submit";
  disabled?: boolean;
}

export function BrutalistButton({
  children,
  onClick,
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  disabled = false,
}: BrutalistButtonProps) {
  const variants = {
    primary: "bg-black text-white border-black hover:bg-black/90",
    secondary: "bg-[#E8FF8B] text-black border-black hover:bg-[#E8FF8B]/90",
    accent: "bg-[#FF6B9D] text-white border-black hover:bg-[#FF6B9D]/90",
    green: "bg-[#8BFFA7] text-black border-black hover:bg-[#8BFFA7]/90",
    terracotta: "bg-[#D4A59A] text-black border-black hover:bg-[#D4A59A]/90",
    grey: "bg-[#9CA3AF] text-black border-black hover:bg-[#888E9B]",
  };

  const sizes = {
    sm: "px-4 py-2 text-sm",
    md: "px-6 py-3",
    lg: "px-8 py-4 text-lg",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`
        ${variants[variant]}
        ${sizes[size]}
        inline-flex items-center justify-center whitespace-nowrap
        border-[3px]
        shadow-[4px_4px_0_0_#0A0A0A]
        transition-all
        hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0_0_#0A0A0A]
        active:translate-x-[4px] active:translate-y-[4px] active:shadow-none
        disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:shadow-[4px_4px_0_0_#0A0A0A]
        ${className}
      `}
    >
      {children}
    </button>
  );
}
