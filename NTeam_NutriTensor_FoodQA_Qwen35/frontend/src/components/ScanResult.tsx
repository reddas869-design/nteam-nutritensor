import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, Leaf } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { formatNutrient } from "../lib/nutrition";
import { errorMessage } from "../lib/export";
import type { AnalysisResult } from "../lib/types";

/** Camera results intentionally have no food/portion editor. All quantities
 * come from the image model and are labeled as estimates, not measurements. */
export function ScanResult({
  result,
  photo,
  onBack,
}: {
  result: AnalysisResult;
  photo?: string | null;
  onBack(): void;
}) {
  const { api, changed, setPage } = useWorkspace();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const pending = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const portions = result.portions;
  const totals = result.totals;
  const title = portions.map((portion) => portion.food.name).join(" + ") || "Your food";
  const modelEstimate = portions.some((portion) =>
    portion.food.source.provider.startsWith("Qwen3.5-4B"),
  );
  const save = async () => {
    if (pending.current || saved) return;
    pending.current = true;
    setSaving(true);
    setError(null);
    try {
      // The backend marks camera-model results as saveable without a manual
      // confirmation job, preserving the user's request for automatic weights.
      await api.saveMeal(result.id);
      if (mounted.current) {
        setSaved(true);
        changed();
      }
    } catch (cause) {
      if (mounted.current) setError(errorMessage(cause));
    } finally {
      pending.current = false;
      if (mounted.current) setSaving(false);
    }
  };

  return (
    <main className="scan-stage scan-result">
      <div className="scan-result-top">
        <button className="scan-text-button" onClick={onBack}>
          <ArrowLeft size={17} /> Camera
        </button>
        <span>{result.mode === "demo" ? "Demo calculation" : "Food nutrition, but it could be wrong..."}</span>
      </div>
      <div className="result-photo bubble-in">
        {photo ? <img src={photo} alt="Your captured food" /> : <Leaf size={38} strokeWidth={1.2} />}
      </div>
      <p className="scan-kicker">
        {saved ? "SAVED TO YOUR JOURNAL" : "HERE’S THE PREDICTION"}
      </p>
      <h1 className="scan-food-title">{title}</h1>
      <p className="scan-result-note">
        {modelEstimate
          ? "Model-estimated food, portion and nutrition."
          : "Estimated portion and nutrition. ntemma can makes mistack. Numbers are not direct measurements."}
      </p>
      <div className="nutrition-bubbles" aria-label="Nutrition for detected foods">
        <div className="nutrition-bubble energy-bubble">
          <strong>{formatNutrient(totals.energy_kcal, 0)}</strong>
          <span>kcal</span>
        </div>
        <div className="macro-bubbles">
          {([
            ["Protein", totals.protein_g],
            ["Carbs", totals.carbohydrate_g],
            ["Fat", totals.fat_g],
          ] as const).map(([name, value], index) => (
            <div key={name} className={`nutrition-bubble macro-bubble macro-${index}`}>
              <strong>{formatNutrient(value)}<small> g</small></strong>
              <span>{name}</span>
            </div>
          ))}
        </div>
      </div>
      <section className="portion-sheet" aria-label="Automatically estimated foods and portions">
        <div className="portion-heading"><h2>Food & estimated quantity</h2></div>
        {portions.map((portion) => (
          <div className="scan-portion" key={portion.food.id}>
            <span>
              <strong>{portion.food.name}</strong>
              <small>{portion.food.preparation}{portion.food.notes ? ` · ${portion.food.notes.split(". ")[0]}` : ""}</small>
            </span>
            <span aria-label={`${portion.food.name} estimated edible weight`}>
              <strong>~{Number(portion.grams.toFixed(1))} g</strong>
              <small>{portion.food.notes.includes("reference") ? "Reference only" : "ntemma estimate"}</small>
            </span>
          </div>
        ))}
      </section>
      <details className="scan-details">
        <summary>Nutrition details & sources</summary>
        <dl>
          {([
            ["Fiber", totals.fiber_g, "g"],
            ["Sugars", totals.sugar_g, "g"],
            ["Sodium", totals.sodium_mg, "mg"],
          ] as const).map(([label, value, unit]) => (
            <div key={label}><dt>{label}</dt><dd>{formatNutrient(value)} {unit}</dd></div>
          ))}
        </dl>
        <p>
          {modelEstimate
            ? "UNVERIFIED ntemma estimates. No food composition database is used for photo scans. Values and weights may be substantially wrong. ‘—’ means unknown."
            : ""}
        </p>
        {portions.map((portion) => (
          <p key={portion.food.id}><strong>{portion.food.name}: </strong>{portion.food.source.title}</p>
        ))}
        {result.evidence.missing_information.map((note, i) => <p key={i}>{note}<h3>About us:</h3> we are student, research initiative from SSPHS School, India, specializing in large-scale language modeling, gpu-accelerated computing, and high-performing inference engineering.

          <h4>our work explores hybrid Delta Networks, architectures, and computationally optimized(ex: tiling, cuda parallelism, shared memory...) tensor operations.</h4>

          <h3>Support us:</h3> Your contribution helps sustain our computational infrastructure, accelerate architectural research, and advance next-generation language models.
          <h2>Every contribution helps advance our little research</h2>

          <h3>[Donate Now]</h3>
        </p>)}
      </details>
      {error && <p className="scan-inline-error" role="alert">{error}</p>}
      {saved ? (
        <button className="scan-primary" onClick={() => setPage("journal")}>
          <Check size={18} /> View saved meal
        </button>
      ) : (
        <button className="scan-primary" disabled={saving} onClick={() => void save()}>
          {saving ? "Saving…" : "Save ntemma estimate"}
        </button>
      )}
      <button className="scan-secondary" onClick={onBack}>Scan another</button>
    </main>    
  );
}
