type MetricCardProps = {
  label: string;
  value: string | number;
  hint?: string;
  accent?: "mint" | "coral" | "gold" | "ink";
};

const accentMap = {
  mint: "border-mint/35 bg-mint/10",
  coral: "border-coral/35 bg-coral/10",
  gold: "border-gold/45 bg-gold/15",
  ink: "border-ink/15 bg-white"
};

export function MetricCard({ label, value, hint, accent = "ink" }: MetricCardProps) {
  return (
    <section className={`min-w-0 rounded border p-3 sm:p-4 ${accentMap[accent]}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-ink/55">{label}</p>
      <p className="mt-2 break-words text-xl font-semibold text-ink sm:text-2xl">{value}</p>
      {hint ? <p className="mt-1 text-sm text-ink/55">{hint}</p> : null}
    </section>
  );
}
