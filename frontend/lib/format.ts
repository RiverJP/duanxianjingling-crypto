export function formatCurrency(value: number): string {
  const absValue = Math.abs(value);
  const maximumFractionDigits =
    absValue >= 1000 ? 0 :
    absValue >= 1 ? 2 :
    absValue >= 0.01 ? 4 :
    absValue >= 0.0001 ? 6 :
    absValue > 0 ? 10 :
    2;
  const minimumFractionDigits = absValue > 0 && absValue < 1 ? maximumFractionDigits : undefined;

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits,
    maximumFractionDigits
  }).format(value);
}

export function formatCompactCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 2
  }).format(value);
}

export function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}
