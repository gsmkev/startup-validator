export function SignalGauge({ score, label }: { score: number; label: string }) {
  // Paraguay flag colors for zones
  const color =
    score > 70
      ? "#6b7280"   // gray — saturated
      : score > 30
      ? "#D52B1E"   // red — opportunity
      : "#0038A8";  // blue — open space

  const radius = 70;
  const circumference = Math.PI * radius; // half circle
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center py-4">
      <svg width="200" height="110" viewBox="0 0 200 110">
        {/* Background arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="16"
          strokeLinecap="round"
        />
        {/* Filled arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={color}
          strokeWidth="16"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.8s ease, stroke 0.4s ease" }}
        />
        {/* Score text */}
        <text x="100" y="90" textAnchor="middle" fontSize="28" fontWeight="bold" fill={color}>
          {score}
        </text>
        <text x="100" y="108" textAnchor="middle" fontSize="10" fill="#9ca3af">
          /100
        </text>
      </svg>
      <span className="text-sm font-semibold mt-1 capitalize" style={{ color }}>
        {label}
      </span>
    </div>
  );
}
