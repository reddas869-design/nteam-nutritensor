import type { JournalEntry } from "./types";
import { NUTRIENTS } from "./nutrition";

export function csvCell(value: unknown): string {
  let text = value == null ? "" : String(value);
  if (/^[\s]*[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function toCsv(entries: JournalEntry[]): string {
  const rows: unknown[][] = [
    [
      "entry_id",
      "eaten_at_utc",
      "meal",
      "meal_type",
      "mode",
      ...NUTRIENTS.map((nutrient) => nutrient.key),
      "notes",
    ],
  ];
  for (const entry of entries) {
    rows.push([
      entry.id,
      entry.eaten_at,
      entry.meal_name,
      entry.meal_type,
      entry.result.mode,
      ...NUTRIENTS.map(({ key }) => entry.result.totals[key]),
      entry.notes,
    ]);
  }
  return rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}
