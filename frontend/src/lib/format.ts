export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds))
  const minutes = Math.floor(s / 60)
  const seconds = s % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export function episodeDuration(seconds: (number | null | undefined)[]): number {
  return seconds.reduce<number>((acc, value) => acc + (value ?? 0), 0)
}

export function formatCost(value: number | null | undefined): string {
  const amount = value ?? 0
  if (amount >= 1) return `$${amount.toFixed(2)}`
  return `$${amount.toFixed(3)}`
}