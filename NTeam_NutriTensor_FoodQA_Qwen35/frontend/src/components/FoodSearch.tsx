import { useState } from "react";
import { Check, Plus, Search } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { useAsync, useDebounce } from "../hooks/useAsync";
import { formatEnergy } from "../lib/nutrition";
import { ErrorNotice, Loading } from "./Primitives";
import type { Food } from "../lib/types";

export function FoodSearch({
  onSelect,
  selected = [],
  compact = false,
}: {
  onSelect(food: Food): void;
  selected?: string[];
  compact?: boolean;
}) {
  const { api } = useWorkspace();
  const [query, setQuery] = useState("");
  const debounced = useDebounce(query);
  const { data, loading, error, reload } = useAsync(
    () => api.foods(debounced),
    [api, debounced],
  );
  return (
    <div className={`food-search ${compact ? "food-search-compact" : ""}`}>
      <label className="search-input">
        <Search size={18} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search rice, dal, paneer…"
          aria-label="Search foods"
          maxLength={200}
        />
      </label>
      <div className="food-search-results">
        {loading && <Loading label="Finding foods" />}
        {error && <ErrorNotice message={error} retry={() => void reload()} />}
        {!loading && data?.length === 0 && (
          <p className="subtle padded">
            No food matched. Try a different name or preparation.
          </p>
        )}
        {!loading &&
          data?.map(({ food }) => {
            const added = selected.includes(food.id);
            return (
              <button
                key={food.id}
                className="food-search-row"
                onClick={() => onSelect(food)}
                disabled={added}
              >
                <span
                  className={`food-category-dot category-${food.category.toLowerCase()}`}
                  aria-hidden="true"
                />
                <span>
                  <strong>{food.name}</strong>
                  <small>
                    {food.preparation} ·{" "}
                    {formatEnergy(food.nutrients.energy_kcal)} kcal / 100 g
                  </small>
                </span>
                {added ? <Check size={17} /> : <Plus size={17} />}
              </button>
            );
          })}
      </div>
    </div>
  );
}
