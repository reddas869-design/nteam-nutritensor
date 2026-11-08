import { useState } from "react";
import { X } from "lucide-react";
import { FoodSearch } from "../components/FoodSearch";
import { ScanStatus } from "../components/ScanStatus";
import { ScanResult } from "../components/ScanResult";
import { useAnalysis } from "../hooks/useAnalysis";
import { useWorkspace } from "../state/workspace";
import type { Food } from "../lib/types";

export default function ManualPage() {
  const { api, preferences } = useWorkspace();
  const [items, setItems] = useState<{ food: Food; grams: string }[]>([]);
  const [description, setDescription] = useState("");
  const modelOnly = api.mode === "live";
  const analysis = useAnalysis();
  const valid = modelOnly
    ? description.trim().length > 1
    : !!items.length &&
      items.every((item) => +item.grams > 0 && +item.grams <= 5000);
  if (analysis.result)
    return <ScanResult result={analysis.result} onBack={analysis.reset} />;
  if (analysis.busy || analysis.error)
    return <ScanStatus failed={!!analysis.error} onBack={analysis.reset} />;
  return (
    <main className="workspace-page simple-page manual-page">
      <p className="scan-kicker">
        {api.mode === "demo"
          ? "MODEL DEMO · EXAMPLE DATA"
          : "MODEL-ESTIMATED NUTRITION"}
      </p>
      <h1>Enter food</h1>
      <p className="simple-intro">{modelOnly
        ? "sir, plz describe your meal and quantities. ntemma will estimate nutrients."
        : "Choose the food, then its edible weight."}</p>
      {modelOnly && (
        <textarea
          className="manual-food-description"
          aria-label="Describe foods and portions"
          placeholder="ex: a cup of cofe"
          maxLength={2000}
          rows={4}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      )}
      {!modelOnly && <FoodSearch
        selected={items.map((item) => item.food.id)}
        onSelect={(food) =>
          setItems((current) =>
            current.some((i) => i.food.id === food.id) || current.length >= 12
              ? current
              : [...current, { food, grams: "100" }],
          )
        }
      />}
      {!modelOnly && items.map((item, index) => (
        <div className="scan-portion" key={item.food.id}>
          <span>
            <strong>{item.food.name}</strong>
            <small>{item.food.preparation}</small>
          </span>
          <label>
            <input
              aria-label={`${item.food.name} grams`}
              type="number"
              min="1"
              max="5000"
              step="any"
              value={item.grams}
              onChange={(event) =>
                setItems((current) =>
                  current.map((i, at) =>
                    at === index ? { ...i, grams: event.target.value } : i,
                  ),
                )
              }
            />
            <span>g</span>
          </label>
          <button
            className="scan-remove"
            aria-label={`Remove ${item.food.name}`}
            onClick={() =>
              setItems((current) => current.filter((_, at) => at !== index))
            }
          >
            <X size={16} />
          </button>
        </div>
      ))}
      <button
        className="scan-primary"
        disabled={!valid}
        onClick={() =>
          void analysis.run({
            description: modelOnly ? description.trim() : "",
            items: modelOnly ? [] : items.map((item) => ({
              food_id: item.food.id,
              grams: +item.grams,
              portion_source: "user_estimate",
              uncertainty_percent: 20,
            })),
            meal_name: modelOnly ? "Described meal" : items
              .map((item) => item.food.name)
              .join(" + ")
              .slice(0, 120),
            meal_type: "snack",
            language: preferences.language,
            detailed: false,
            confirmed: false,
          })
        }
      >
        See nutrition from ntemma
      </button>
    </main>
  );
}
