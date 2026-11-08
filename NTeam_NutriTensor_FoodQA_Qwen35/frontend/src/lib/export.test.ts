import { describe, expect, it } from "vitest";
import { csvCell, toCsv } from "./export";

describe("portable CSV export", () => {
  it.each([
    "=SUM(1,2)",
    "+cmd",
    "-cmd",
    "@formula",
    '  =HYPERLINK("x")',
    "\tformula",
    "\rformula",
  ])("neutralizes spreadsheet formula prefixes: %s", (value) => {
    expect(csvCell(value)).toMatch(/^"'/);
  });

  it("escapes quotes, line breaks and delimiters without losing text", () => {
    expect(csvCell('Rice, "dal"\nvegetables')).toBe(
      '"Rice, ""dal""\nvegetables"',
    );
    expect(csvCell("ভাত")).toBe('"ভাত"');
    expect(csvCell(null)).toBe('""');
    expect(csvCell(0)).toBe('"0"');
  });

  it("exports a useful schema even when the journal is empty", () => {
    const result = toCsv([]);
    expect(result).toContain('"eaten_at_utc"');
    expect(result).toContain('"sodium_mg"');
    expect(result.split("\r\n")).toHaveLength(1);
  });
});
