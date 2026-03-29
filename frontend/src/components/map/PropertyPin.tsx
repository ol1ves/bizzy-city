'use client';

// Color-code by analysis status:
//   Analyzed & high score (>=70): warm coral
//   Analyzed & medium score (40-69): muted tan
//   Analyzed & low score (<40): soft peach
//   Not yet analyzed: soft sky blue (inviting action)
const PIN_COLORS = {
  high: '#E8654A',      // warm coral - high score
  medium: '#C4956A',    // muted tan - medium score
  low: '#E8B4A0',       // soft peach - low score
  unanalyzed: '#7CB9D8', // soft sky blue - not yet analyzed
};

function getPinColor(score: number | null): string {
  if (score === null) return PIN_COLORS.unanalyzed;
  if (score >= 70) return PIN_COLORS.high;
  if (score >= 40) return PIN_COLORS.medium;
  return PIN_COLORS.low;
}

interface PropertyPinProps {
  score?: number | null;
  isHovered?: boolean;
}

export default function PropertyPin({ score = null, isHovered = false }: PropertyPinProps) {
  const color = getPinColor(score);
  
  return (
    <div 
      className={`cursor-pointer transition-transform ${isHovered ? 'scale-110' : ''}`}
      style={{ filter: isHovered ? 'drop-shadow(0 4px 6px rgba(0,0,0,0.3))' : 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))' }}
    >
      <svg width="32" height="40" viewBox="0 0 32 40" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path 
          d="M16 0C7.16 0 0 6.72 0 15C0 26.25 16 40 16 40S32 26.25 32 15C32 6.72 24.84 0 16 0Z" 
          fill={color}
        />
        <rect x="9" y="9" width="14" height="11" rx="1.5" fill="white" opacity="0.9"/>
        <path d="M9 14.5h14" stroke={color} strokeWidth="1"/>
        <rect x="13" y="16" width="6" height="4" rx="0.5" fill={color} opacity="0.3"/>
      </svg>
    </div>
  );
}
