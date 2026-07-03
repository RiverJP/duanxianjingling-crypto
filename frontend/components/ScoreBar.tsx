type ScoreBarProps = {
  label: string;
  value: number;
  tone?: "mint" | "coral" | "gold";
};

const toneMap = {
  mint: "bg-mint",
  coral: "bg-coral",
  gold: "bg-gold"
};

export function ScoreBar({ label, value, tone = "mint" }: ScoreBarProps) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium text-ink/75">{label}</span>
        <span className="tabular-nums text-ink">{value}/100</span>
      </div>
      <div className="h-2 rounded bg-ink/10">
        <div className={`h-2 rounded ${toneMap[tone]}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}
