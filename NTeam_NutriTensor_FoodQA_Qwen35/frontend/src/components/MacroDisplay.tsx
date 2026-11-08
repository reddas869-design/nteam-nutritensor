import {
  formatEnergy,
  formatNutrient,
  macroShares,
  NUTRIENTS,
} from "../lib/nutrition";
import type { Nutrients } from "../lib/types";

export function MacroDisplay({
  nutrients,
  compact = false,
}: {
  nutrients: Nutrients;
  compact?: boolean;
}) {
  return (
    <div className={`macro-display ${compact ? "macro-compact" : ""}`}>
      {!compact && (
        <div className="energy-number">
          <span>{formatEnergy(nutrients.energy_kcal)}</span>
          <small>
            kcal <span>estimated energy</span>
          </small>
        </div>
      )}
      <div className="macro-grid">
        {NUTRIENTS.slice(1, 4).map(({ key, label, unit, color }) => (
          <div key={key} className="macro-cell">
            <span className="macro-label">
              <i style={{ background: color }} />
              {label === "Carbohydrate" ? "Carbs" : label}
            </span>
            <strong>
              {formatNutrient(nutrients[key])}
              <small>{unit}</small>
            </strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MacroBar({ nutrients }: { nutrients: Nutrients }) {
  const shares = macroShares(nutrients);
  if (!shares.length)
    return (
      <p className="subtle">
        Macro proportions are unavailable because a source value is missing.
      </p>
    );
  return (
    <div className="macro-proportion">
      <div
        className="macro-bar"
        role="img"
        aria-label={shares
          .map(
            (item) =>
              `${item.name}: ${Math.round(item.share * 100)} percent of estimated macro energy`,
          )
          .join(", ")}
      >
        {shares.map((item) => (
          <span
            key={item.name}
            style={{ flex: item.share, background: item.color }}
          />
        ))}
      </div>
    </div>
  );
}

export function NutrientTable({ nutrients }: { nutrients: Nutrients }) {
  return (
    <div className="nutrient-table">
      {NUTRIENTS.map(({ key, label, unit }) => (
        <div key={key}>
          <span>{label}</span>
          <strong>
            {formatNutrient(nutrients[key])} <small>{unit}</small>
          </strong>
        </div>
      ))}
    </div>
  );
}
