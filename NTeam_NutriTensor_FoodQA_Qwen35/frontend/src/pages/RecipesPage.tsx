import { useState } from "react";
import { ChefHat, Leaf, Plus, Trash2 } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { useAsync } from "../hooks/useAsync";
import { formatEnergy, formatNutrient, scale } from "../lib/nutrition";
import { errorMessage } from "../lib/export";
import type { Food, Recipe, RecipeInput } from "../lib/types";
import {
  Button,
  EmptyState,
  ErrorNotice,
  Field,
  IconButton,
  Loading,
  Modal,
  PageHeading,
} from "../components/Primitives";
import { FoodSearch } from "../components/FoodSearch";
import { MacroDisplay, NutrientTable } from "../components/MacroDisplay";

export default function RecipesPage() {
  const { api, revision, changed, toast } = useWorkspace();
  const { data, loading, error, reload } = useAsync(
    () => api.recipes(),
    [api, revision],
  );
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<Recipe | null>(null);
  const [deleting, setDeleting] = useState<Recipe | null>(null);
  const [name, setName] = useState("");
  const [weight, setWeight] = useState(500);
  const [servings, setServings] = useState(2);
  const [notes, setNotes] = useState("");
  const [ingredients, setIngredients] = useState<
    { food: Food; grams: number }[]
  >([]);
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const add = (food: Food) =>
    setIngredients((current) =>
      current.some((item) => item.food.id === food.id)
        ? current
        : [...current, { food, grams: 100 }],
    );
  const create = async () => {
    setPending(true);
    setFormError(null);
    const request: RecipeInput = {
      name: name.trim(),
      ingredients: ingredients.map((item) => ({
        food_id: item.food.id,
        grams: item.grams,
      })),
      cooked_weight_g: weight,
      servings,
      notes,
    };
    try {
      const recipe = await api.createRecipe(request);
      setCreating(false);
      setSelected(recipe);
      setIngredients([]);
      setName("");
      changed();
      toast("Recipe saved", "success");
    } catch (cause) {
      setFormError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  };
  const remove = async () => {
    if (!deleting) return;
    setPending(true);
    try {
      await api.deleteRecipe(deleting.id);
      setDeleting(null);
      changed();
    } catch (cause) {
      toast(errorMessage(cause), "error");
    } finally {
      setPending(false);
    }
  };
  const valid =
    name.trim() &&
    weight > 0 &&
    weight <= 50000 &&
    servings >= 1 &&
    servings <= 100 &&
    Number.isInteger(servings) &&
    ingredients.length > 0 &&
    ingredients.every((item) => item.grams > 0 && item.grams <= 20000);
  return (
    <main className="workspace-page recipes-page">
      <PageHeading
        eyebrow="MAKE IT YOUR OWN"
        title="From your kitchen."
        text="Build a recipe from ingredients. Weigh the finished dish to calculate each serving."
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus size={17} />
            New recipe
          </Button>
        }
      />
      {loading && <Loading />}
      {error && <ErrorNotice message={error} retry={() => void reload()} />}
      {!loading && data?.length === 0 && (
        <EmptyState
          icon={<ChefHat size={34} />}
          title="Your dal. Your recipe."
          text="Different recipes deserve different numbers. Add ingredients, oil and the final cooked weight to make yours."
          action="Create a recipe"
          onAction={() => setCreating(true)}
        />
      )}
      <div className="recipe-grid">
        {data?.map((recipe) => (
          <article key={recipe.id} className="recipe-card">
            <div className="recipe-symbol">
              <Leaf size={30} strokeWidth={1.3} />
            </div>
            <div className="recipe-card-head">
              <small>
                {recipe.ingredients.length} ingredients · {recipe.servings}{" "}
                servings
              </small>
              <IconButton
                label={`Delete ${recipe.name}`}
                onClick={() => setDeleting(recipe)}
              >
                <Trash2 size={15} />
              </IconButton>
            </div>
            <button
              className="recipe-title"
              onClick={() => setSelected(recipe)}
            >
              <h2>{recipe.name}</h2>
            </button>
            <p>{recipe.notes || "A recipe from your kitchen."}</p>
            <div className="recipe-values">
              <strong>
                {formatEnergy(
                  recipe.total.energy_kcal === null
                    ? null
                    : recipe.total.energy_kcal / recipe.servings,
                )}
                <small>kcal / serving</small>
              </strong>
              <span>
                {formatNutrient(recipe.cooked_weight_g / recipe.servings, 0)} g
                per serving
              </span>
            </div>
            <Button variant="secondary" onClick={() => setSelected(recipe)}>
              View recipe
            </Button>
          </article>
        ))}
      </div>
      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title="Build your recipe"
        description="Use weights for the actual ingredients. Include added oil and sauces."
        wide
      >
        <div className="recipe-builder">
          <div>
            <Field label="Recipe name">
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={150}
                placeholder="Our everyday dal"
              />
            </Field>
            <FoodSearch
              compact
              onSelect={add}
              selected={ingredients.map((item) => item.food.id)}
            />
          </div>
          <div>
            <h3 className="form-section-title">Ingredients</h3>
            {!ingredients.length && (
              <p className="subtle padded">
                Choose foods from the search to start.
              </p>
            )}
            {ingredients.map((item) => (
              <div className="selected-food" key={item.food.id}>
                <span>{item.food.name}</span>
                <label>
                  <input
                    aria-label={`${item.food.name} ingredient grams`}
                    type="number"
                    min="1"
                    max="20000"
                    value={item.grams || ""}
                    onChange={(event) =>
                      setIngredients((current) =>
                        current.map((value) =>
                          value.food.id === item.food.id
                            ? { ...value, grams: Number(event.target.value) }
                            : value,
                        ),
                      )
                    }
                  />
                  <small>g</small>
                </label>
                <IconButton
                  label={`Remove ${item.food.name}`}
                  onClick={() =>
                    setIngredients((current) =>
                      current.filter((value) => value.food.id !== item.food.id),
                    )
                  }
                >
                  <Trash2 size={14} />
                </IconButton>
              </div>
            ))}
            <div className="form-grid">
              <Field
                label="Cooked weight (g)"
                hint="Weigh the whole finished dish."
              >
                <input
                  type="number"
                  min="1"
                  max="50000"
                  value={weight || ""}
                  onChange={(event) => setWeight(Number(event.target.value))}
                />
              </Field>
              <Field label="Servings">
                <input
                  type="number"
                  min="1"
                  max="100"
                  step="1"
                  value={servings || ""}
                  onChange={(event) => setServings(Number(event.target.value))}
                />
              </Field>
            </div>
            <Field label="Notes">
              <textarea
                value={notes}
                maxLength={2000}
                onChange={(event) => setNotes(event.target.value)}
                rows={2}
                placeholder="Preparation, substitutions, a family tip…"
              />
            </Field>
          </div>
        </div>
        <div className="notice">
          <p>
            Recipe arithmetic assumes all entered ingredients remain in the
            final dish. losses need separate
            adjustments.
          </p>
        </div>
        {formError && <ErrorNotice message={formError} />}
        <div className="modal-footer">
          <Button variant="ghost" onClick={() => setCreating(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => void create()}
            loading={pending}
            disabled={!valid}
          >
            Calculate & save
          </Button>
        </div>
      </Modal>
      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.name ?? "Recipe"}
        description="A recipe calculated from your selected source records."
      >
        {selected && (
          <>
            <p className="eyebrow">
              PER SERVING ·{" "}
              {formatNutrient(selected.cooked_weight_g / selected.servings)} G
            </p>
            <MacroDisplay
              nutrients={scale(selected.total, 1 / selected.servings)}
            />
            <details className="more-nutrients">
              <summary>
                Per 100 g values
                <Plus size={15} />
              </summary>
              <NutrientTable nutrients={selected.per_100g} />
            </details>
            <div className="recipe-source-list">
              <h3>Ingredient sources</h3>
              {selected.sources.map((source, index) => (
                <div key={index}>
                  <strong>{source.title}</strong>
                  <small>
                    {source.provider} · {source.record_id}
                  </small>
                </div>
              ))}
            </div>
            {selected.notes && (
              <p className="subtle padded">{selected.notes}</p>
            )}
            <div className="modal-footer">
              <Button onClick={() => setSelected(null)}>Done</Button>
            </div>
          </>
        )}
      </Modal>
      <Modal
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Delete this recipe?"
        description="This removes the saved recipe from your workspace."
      >
        <div className="modal-footer">
          <Button variant="ghost" onClick={() => setDeleting(null)}>
            Keep recipe
          </Button>
          <Button
            variant="danger"
            loading={pending}
            onClick={() => void remove()}
          >
            Delete recipe
          </Button>
        </div>
      </Modal>
    </main>
  );
}
