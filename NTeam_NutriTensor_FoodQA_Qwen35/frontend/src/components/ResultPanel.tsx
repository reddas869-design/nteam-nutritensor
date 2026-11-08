import { useEffect, useMemo, useState } from "react";
import {
  Bookmark,
  Check,
  ChevronDown,
  ExternalLink,
  FileCheck2,
  Plus,
  Scale,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import { useWorkspace } from "../state/workspace";
import {
  calculatePortion,
  formatEnergy,
  formatNutrient,
  resultSelections,
  sumNutrients,
} from "../lib/nutrition";
import { errorMessage } from "../lib/export";
import type {
  AnalysisRequest,
  AnalysisResult,
  Food,
  FoodSelection,
  JobEvent,
} from "../lib/types";
import { Badge, Button, IconButton, Modal } from "./Primitives";
import { MacroBar, MacroDisplay, NutrientTable } from "./MacroDisplay";
import { FoodSearch } from "./FoodSearch";
import { ChatPanel } from "./ChatPanel";
import { stageLabels } from "../lib/defaults";

export function ResultPanel({
  result,
  events = [],
  onClose,
  onRecalculate,
  readOnly = false,
}: {
  result: AnalysisResult;
  events?: JobEvent[];
  onClose(): void;
  onRecalculate(request: AnalysisRequest): void;
  readOnly?: boolean;
}) {
  const { api, preferences, toast, changed } = useWorkspace();
  const [tab, setTab] = useState<"overview" | "evidence" | "activity">(
    "overview",
  );
  const [selections, setSelections] = useState<FoodSelection[]>(
    resultSelections(result),
  );
  const [foods, setFoods] = useState<Food[]>(
    result.portions.map((portion) => portion.food),
  );
  const [expanded, setExpanded] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    setSelections(resultSelections(result));
    setFoods(result.portions.map((portion) => portion.food));
    setSaved(false);
  }, [result.id]);
  const dirty =
    JSON.stringify(selections) !== JSON.stringify(resultSelections(result));
  const invalid = selections.some(
    (item) =>
      !Number.isFinite(item.grams) || item.grams <= 0 || item.grams > 5000,
  );
  const portions = useMemo(
    () =>
      selections.map((selection) => {
        const food = foods.find((item) => item.id === selection.food_id)!;
        return calculatePortion(food, {
          ...selection,
          grams:
            selection.grams > 0 && selection.grams <= 5000
              ? selection.grams
              : 100,
        });
      }),
    [selections, foods],
  );
  const totals = sumNutrients(portions.map((portion) => portion.nutrients));
  const lower = sumNutrients(portions.map((portion) => portion.lower));
  const upper = sumNutrients(portions.map((portion) => portion.upper));
  const update = (foodId: string, patch: Partial<FoodSelection>) =>
    setSelections((current) =>
      current.map((selection) =>
        selection.food_id === foodId ? { ...selection, ...patch } : selection,
      ),
    );
  const recalculate = () =>
    onRecalculate({
      description: "",
      items: selections,
      meal_name: result.meal_name,
      meal_type: result.meal_type,
      language: preferences.language,
      detailed: true,
      confirmed: true,
    });
  const save = async () => {
    setSaving(true);
    try {
      await api.saveMeal(result.id);
      setSaved(true);
      changed();
      toast("Meal saved to your journal", "success");
    } catch (cause) {
      toast(errorMessage(cause), "error");
    } finally {
      setSaving(false);
    }
  };
  const add = (food: Food) => {
    if (selections.some((selection) => selection.food_id === food.id)) return;
    setFoods((current) => [...current, food]);
    setSelections((current) => [
      ...current,
      {
        food_id: food.id,
        grams: food.servings[0]?.grams ?? 100,
        portion_source: "user_estimate",
        uncertainty_percent: 20,
      },
    ]);
  };
  return (
    <aside className="result-panel" aria-label="Meal analysis result">
      <header className="result-header">
        <div>
          <p className="eyebrow">
            {result.mode === "demo" ? "EXAMPLE ANALYSIS" : "MEAL ANALYSIS"}
          </p>
          {/* <h2>{result.meal_name}</h2> */}
        </div>
        <IconButton label="Close result" onClick={onClose}>
          <X size={20} />
        </IconButton>
      </header>
      <div className="result-meta">
        <Badge tone="green">
          <Check size={12} />
          {result.portions.length} foods matched
        </Badge>
      </div>
      <div className="result-tabs" role="tablist" aria-label="Result details">
        {(["overview", "evidence", "activity"] as const).map((value) => (
          <button
            role="tab"
            aria-selected={tab === value}
            aria-controls={`result-${value}`}
            key={value}
            onClick={() => setTab(value)}
          >
            {value === "overview"
              ? "Over view"
              : value === "evidence"
                ? "sources & checks"
                : "activity"}
          </button>
        ))}
      </div>
      <div className="result-scroll">
        {tab === "overview" && (
          <div id="result-overview" role="tabpanel">
            <MacroDisplay nutrients={totals} />
            <div className="range-note">
              <span className="range-dot" />
              <span>
                Portion range{" "}
                <strong>
                  {formatEnergy(lower.energy_kcal)}–
                  {formatEnergy(upper.energy_kcal)} kcal
                </strong>
              </span>
            </div>
            <MacroBar nutrients={totals} />
            <div className="section-title">
              <h3>In our hand</h3>
              <span>
                {readOnly ? "Saved portions" : "Tap a food to adjust"}
              </span>
            </div>
            <div className="portion-list">
              {portions.map((portion) => {
                const selection = selections.find(
                  (item) => item.food_id === portion.food.id,
                )!;
                return (
                  <div className="portion-card" key={portion.food.id}>
                    <button
                      className="portion-summary"
                      onClick={() =>
                        setExpanded((current) =>
                          current === portion.food.id ? null : portion.food.id,
                        )
                      }
                      aria-expanded={expanded === portion.food.id}
                    >
                      <span
                        className={`food-category-dot category-${portion.food.category.toLowerCase()}`}
                      />
                      <span>
                        <strong>{portion.food.name}</strong>
                        <small>
                          {selection.grams || "—"} g ·{" "}
                          {portion.food.preparation}
                        </small>
                      </span>
                      <strong>
                        {formatEnergy(portion.nutrients.energy_kcal)}
                        <small>kcal</small>
                      </strong>
                      <ChevronDown
                        size={15}
                        className={expanded === portion.food.id ? "rotate" : ""}
                      />
                    </button>
                    {expanded === portion.food.id && (
                      <div className="portion-editor">
                        {!readOnly && (
                          <>
                            <label className="portion-grams">
                              Portion weight
                              <span>
                                <input
                                  aria-label={`${portion.food.name} weight in grams`}
                                  type="number"
                                  min="1"
                                  max="5000"
                                  value={selection.grams || ""}
                                  onChange={(event) =>
                                    update(portion.food.id, {
                                      grams: Number(event.target.value),
                                    })
                                  }
                                />
                                <small>g</small>
                              </span>
                            </label>
                            <input
                              className="portion-slider"
                              aria-label={`${portion.food.name} portion slider`}
                              type="range"
                              min="10"
                              max="500"
                              step="5"
                              value={Math.min(
                                500,
                                Math.max(10, selection.grams),
                              )}
                              onChange={(event) =>
                                update(portion.food.id, {
                                  grams: Number(event.target.value),
                                })
                              }
                            />
                            <div className="portion-controls">
                              <label>
                                <Scale size={14} />
                                <select
                                  aria-label="Portion measurement"
                                  value={selection.portion_source}
                                  onChange={(event) =>
                                    update(portion.food.id, {
                                      portion_source: event.target
                                        .value as FoodSelection["portion_source"],
                                      uncertainty_percent:
                                        event.target.value === "weighed"
                                          ? 2
                                          : 20,
                                    })
                                  }
                                >
                                  <option value="weighed">Weighed</option>
                                  <option value="user_estimate">
                                    Estimated
                                  </option>
                                  <option value="label">Package label</option>
                                  {selection.portion_source ===
                                    "image_estimate" && (
                                    <option value="image_estimate">
                                      Image estimate
                                    </option>
                                  )}
                                </select>
                              </label>
                              <button
                                className="text-button danger-text"
                                onClick={() =>
                                  setSelections((current) =>
                                    current.filter(
                                      (item) =>
                                        item.food_id !== portion.food.id,
                                    ),
                                  )
                                }
                              >
                                <Trash2 size={14} />
                                Remove
                              </button>
                            </div>
                          </>
                        )}
                        <MacroDisplay nutrients={portion.nutrients} compact />
                        
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            {!readOnly && (
              <button
                className="text-button add-food"
                onClick={() => setAdding(true)}
              >
                <Plus size={16} />
                Add another food
              </button>
            )}
            <section className="meal-insight">
              <div>
                <FileCheck2 size={18} />
                <h3>A little context</h3>
              </div>
              <p>
                {dirty
                  ? "Recalculate to update the explanation and save these portions."
                  : result.explanation}
              </p>
            </section>
            <details className="more-nutrients">
              <summary>
                Full nutrient breakdown
                <Plus size={15} />
              </summary>
              <NutrientTable nutrients={totals} />
            </details>
            {result.mode === "demo" && (
              <p className="fine-print demo-disclaimer">                
              </p>
            )}
            <ChatPanel analysisId={result.id} />
          </div>
        )}
        {tab === "evidence" && (
          <div id="result-evidence" role="tabpanel" className="evidence-panel">
            <div className="evidence-intro">
              <FileCheck2 size={24} />
              <h3>Every number has a source(from ntemma).</h3>
              <p></p>
            </div>
            {result.portions.map((portion) => (
              <details className="source-card" key={portion.food.id}>
                <summary>
                  <span>
                    <strong>{portion.food.name}</strong>
                    <small>{portion.food.source.provider}</small>
                  </span>
                  <ChevronDown size={16} />
                </summary>
                <div>
                  <p>{portion.food.source.title}</p>
                  <dl>
                    <dt>Record</dt>
                    <dd>ntemma:private</dd>
                    <dt>Basis</dt>
                    <dd>Per 100 g</dd>
                    <dt>Retrieved</dt>
                    <dd>{portion.food.source.retrieved_at.slice(0, 10)}</dd>
                    <dt>License</dt>
                    <dd>{portion.food.source.license}</dd>
                  </dl>
                  {portion.food.source.url && (
                    <a
                      href={portion.food.source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-button"
                    >
                      Open source
                      <ExternalLink size={14} />
                    </a>
                  )}
                </div>
              </details>
            ))}
            {/* <EvidenceList
              title="How this was calculated"
              items={result.evidence.statements}
            />
            <EvidenceList
              title="Assumptions to review"
              items={result.evidence.assumptions}
            />
            <EvidenceList
              title="What we don't know"
              items={result.evidence.missing_information}
            /> */}
            {result.flags.map((flag, index) => (
              <div
                key={`${flag.code}-${index}`}
                className={`notice ${flag.severity === "warning" ? "notice-amber" : ""}`}
              >
                <p>{flag.message}</p>
              </div>
            ))}
          </div>
        )}
        {tab === "activity" && (
          <div id="result-activity" role="tabpanel" className="activity-panel">
            <div className="section-title">
              <h3>Analysis activity</h3>
              <Badge>
                {result.mode === "demo" ? "Demo workflow" : "Local pipeline"}
              </Badge>
            </div>
            <p className="subtle">
              Task progress, checks and evidence.</p>
            {events.length ? (
              <ol className="activity-list">
                {events
                  .filter((event) => event.state !== "started")
                  .map((event) => (
                    <li key={event.sequence}>
                      <Check size={14} />
                      <div>
                        <strong>{stageLabels[event.stage]}</strong>
                        <p>{event.message}</p>
                      </div>
                    </li>
                  ))}
              </ol>
            ) : (
              <p className="subtle padded">                
              </p>
            )}
            {result.mode === "live" ? (
              <div className="runtime-grid">
                <Metric
                  label="Total work"
                  value={`${(result.stats.total_ms / 1000).toFixed(2)} s`}
                />
                <Metric
                  label="Queue wait"
                  value={`${(result.stats.queue_ms / 1000).toFixed(2)} s`}
                />
                <Metric
                  label="Generation"
                  value={
                    result.stats.tokens_per_second
                      ? `${result.stats.tokens_per_second.toFixed(1)} tok/s`
                      : "Not measured"
                  }
                />
                <Metric
                  label="Peak allocation"
                  value={
                    result.stats.gpu_peak_mb
                      ? `${Math.round(result.stats.gpu_peak_mb)} MB`
                      : "Not measured"
                  }
                />
                <Metric
                  label="Prompt tokens"
                  value={String(result.stats.prompt_tokens)}
                />
                <Metric
                  label="Output tokens"
                  value={String(result.stats.completion_tokens)}
                />
              </div>
            ) : (
              <div className="notice">
                <p>
                  No GPU timings are claimed in demo mode. Connect our model to
                  collect real measurements.
                </p>
              </div>
            )}
            <p className="fine-print">
              the full model lager calculation(ex: tensor, 81.25% of speed of light, harder optimization maths technique and many more) runs on a local server, which has a electricity costs.
            </p>
            {result.evidence.missing_information.map((note, i) => <p key={i}>{note}<h3>About us:</h3> we are student, research initiative from SSPHS School, India, specializing in large-scale language modeling, gpu-accelerated computing, and high-performing inference engineering.

          <h4>our work explores hybrid Gated Delta Networks, sparse Mixture-of-Experts architectures, and computationally optimized tensor operations.</h4>

          <h3>Support Our Little team:</h3> Your contribution helps sustain our computational infrastructure, accelerate architectural research, and advance next-generation language models.
          <h2>Every contribution helps advance our little research</h2>

          <h4>[Donate Now]</h4>
        </p>)}
          </div>
        )}
      </div>
      {!readOnly && (
        <footer className="result-footer">
          {result.needs_confirmation || dirty ? (
            <Button
              onClick={recalculate}
              disabled={invalid || !selections.length}
            >
              <SlidersHorizontal size={17} />
              {dirty ? "Recalculate portions" : "Confirm foods & portions"}
            </Button>
          ) : (
            <Button
              onClick={() => void save()}
              loading={saving}
              disabled={saved}
            >
              {saved ? <Check size={17} /> : <Bookmark size={17} />}
              {saved ? "Saved to journal" : "Save this meal"}
            </Button>
          )}
          <p>
            {invalid
              ? "Enter a valid weight between 1 and 5,000 g."
              : result.needs_confirmation
                ? "Check preparation and grams before confirming."
                : "sir, your meal stays in your workspace."}
          </p>
        </footer>
      )}
      <Modal
        open={adding}
        onClose={() => setAdding(false)}
        title="Add a food"
        description="Choose the closest preparation from your catalog."
      >
        <FoodSearch
          onSelect={add}
          selected={selections.map((item) => item.food_id)}
        />
        <div className="modal-footer">
          <Button onClick={() => setAdding(false)}>Done</Button>
        </div>
      </Modal>
    </aside>
  );
}

function EvidenceList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="evidence-list">
      <h3>{title}</h3>
      <ul>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}
