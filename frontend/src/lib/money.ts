/** "12,50" or "12.5" → 1250 cents; `null` when the text is not a non-negative amount. */
export function toCents(text: string): number | null {
  const normalised = text.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(normalised)) return null;
  return Math.round(parseFloat(normalised) * 100);
}

export function euros(cents: number | null): string {
  return cents === null ? "—" : `${(cents / 100).toFixed(2).replace(".", ",")} €`;
}
