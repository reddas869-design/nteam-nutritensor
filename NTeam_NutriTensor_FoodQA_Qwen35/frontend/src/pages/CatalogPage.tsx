import { useState } from "react";
import {
  ArrowUpRight,
  Database,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { useAsync, useDebounce } from "../hooks/useAsync";
import { formatEnergy, formatNutrient } from "../lib/nutrition";
import type { Food } from "../lib/types";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  Modal,
  PageHeading,
} from "../components/Primitives";
import { NutrientTable } from "../components/MacroDisplay";

export default function CatalogPage() {
  const { api, capabilities } = useWorkspace();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [selected, setSelected] = useState<Food | null>(null);
  const needle = useDebounce(query);
  const { data, loading, error, reload } = useAsync(
    () => api.foods(needle, category || undefined),
    [api, needle, category],
  );
  const categories = useAsync(() => api.categories(), [api]);
  return (
    <main className="workspace-page catalog-page">
      <PageHeading
        eyebrow="TRACE IT TO THE SOURCE"
        title="The food library."
        text="Look beyond the headline numbers. Preparation, units and provenance matter."
        action={
          <Badge tone={api.mode === "demo" ? "amber" : "green"}>
            <Database size={13} />
            {api.mode === "demo"
              ? "Illustrative catalog"
              : `${capabilities?.catalog_count ?? 0} source records`}
          </Badge>
        }
      />
      <div className="catalog-toolbar">
        <label className="search-input">
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search the food catalog"
            placeholder="Find a food or ingredient…"
            maxLength={200}
          />
        </label>
        <label className="category-select">
          <SlidersHorizontal size={16} />
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            aria-label="Filter food category"
          >
            <option value="">All categories</option>
            {categories.data?.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
      </div>
      {loading && <Loading label="Opening the food library" />}
      {error && <ErrorNotice message={error} retry={() => void reload()} />}
      {!loading && data?.length === 0 && (
        <EmptyState
          icon={<Search size={30} />}
          title="No matching food yet."
          text="Try another name or import additional verified records into your local catalog."
        />
      )}
      <div className="catalog-grid">
        {data?.map(({ food }) => (
          <button
            key={food.id}
            className="catalog-card"
            onClick={() => setSelected(food)}
          >
            <div className="catalog-card-top">
              <span
                className={`food-category-dot category-${food.category.toLowerCase()}`}
              />
              <small>{food.category}</small>
              <ArrowUpRight size={16} />
            </div>
            <h2>{food.name}</h2>
            <span className="catalog-preparation">{food.preparation}</span>
            <div className="catalog-energy">
              <strong>{formatEnergy(food.nutrients.energy_kcal)}</strong>
              <span>kcal / 100 g</span>
            </div>
            <div className="catalog-macros">
              <span>
                P <strong>{formatNutrient(food.nutrients.protein_g)}g</strong>
              </span>
              <span>
                C{" "}
                <strong>
                  {formatNutrient(food.nutrients.carbohydrate_g)}g
                </strong>
              </span>
              <span>
                F <strong>{formatNutrient(food.nutrients.fat_g)}g</strong>
              </span>
            </div>
            <span className="catalog-source">{food.source.provider}</span>
          </button>
        ))}
      </div>
      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.name ?? "Food record"}
        description="Nutrition values for 100 g of the selected preparation."
      >
        {selected && (
          <>
            <div className="food-record-tags">
              <Badge>{selected.category}</Badge>
              <Badge>{selected.preparation}</Badge>
              {selected.source.is_demo && (
                <Badge tone="amber">Demo fixture</Badge>
              )}
            </div>
            <NutrientTable nutrients={selected.nutrients} />
            <div className="record-source">
              <h3>{selected.source.provider}</h3>
              <p>{selected.source.title}</p>
              <dl>
                <dt>Record ID</dt>
                <dd>{selected.source.record_id}</dd>
                <dt>Retrieved</dt>
                <dd>{selected.source.retrieved_at.slice(0, 10)}</dd>
                <dt>License</dt>
                <dd>{selected.source.license}</dd>
              </dl>
              {selected.source.url && (
                <a
                  className="text-button"
                  href={selected.source.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open original record
                  <ArrowUpRight size={15} />
                </a>
              )}
            </div>
            {selected.servings.length > 0 && (
              <div className="record-servings">
                <h3>Source portions</h3>
                {selected.servings.map((serving) => (
                  <p key={serving.label}>
                    {serving.label}
                    <strong>{serving.grams} g</strong>
                  </p>
                ))}
              </div>
            )}
            <p className="fine-print padded">{selected.notes}</p>
            <p className="fine-print">
              An empty allergen field does not mean a food is allergen-free.
            </p>
          </>
        )}
      </Modal>
    </main>
  );
}
