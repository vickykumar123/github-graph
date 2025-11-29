interface GitWalkIconProps {
  className?: string;
}

export default function GitWalkIcon({ className = "w-8 h-8" }: GitWalkIconProps) {
  return (
    <svg className={className} viewBox="0 0 100 100" fill="none">
      {/* Background circle */}
      <circle cx="50" cy="50" r="45" fill="#0a0a0f" stroke="#1f1f2e" strokeWidth="2"/>

      {/* Code brackets */}
      <path d="M30 35 L20 50 L30 65" stroke="#a855f7" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      <path d="M70 35 L80 50 L70 65" stroke="#ec4899" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" fill="none"/>

      {/* Network nodes */}
      <circle cx="40" cy="40" r="6" fill="#a855f7"/>
      <circle cx="60" cy="40" r="6" fill="#ec4899"/>
      <circle cx="50" cy="55" r="7" fill="#3b82f6"/>
      <circle cx="40" cy="68" r="5" fill="#a855f7" opacity="0.7"/>
      <circle cx="60" cy="68" r="5" fill="#ec4899" opacity="0.7"/>

      {/* Connecting lines */}
      <path d="M40 46 L50 50 M60 46 L50 50 M50 62 L40 65 M50 62 L60 65" stroke="white" strokeOpacity="0.4" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}
