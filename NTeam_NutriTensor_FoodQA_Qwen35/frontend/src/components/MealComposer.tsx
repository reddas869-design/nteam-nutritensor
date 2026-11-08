import { useEffect, useState } from "react";
import { ArrowRight, Plus, Trash2 } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { Button, Field, IconButton, Modal, Toggle } from "./Primitives";
import { FoodSearch } from "./FoodSearch";
import type {
  AnalysisRequest,
  Food,
  FoodSelection,
  MealType,
} from "../lib/types";

export function MealComposer({
  open,
  onClose,
  onSubmit,
  imageId,
  initialDescription = "",
}: {
  open: boolean;
  onClose(): void;
  onSubmit(request: AnalysisRequest): void;
  imageId?: string;
  initialDescription?: string;
}) {
  const { preferences, capabilities, api } = useWorkspace();
  const [description, setDescription] = useState(initialDescription);
  const [name, setName] = useState("My meal");
  const [type, setType] = useState<MealType>("lunch");
  const [items, setItems] = useState<
    { food: Food; selection: FoodSelection }[]
  >([]);
  const [detailed, setDetailed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  useEffect(() => {
    if (open) setDescription(initialDescription);
  }, [open, initialDescription]);
  const add = (food: Food) => {
    if (items.some((item) => item.food.id === food.id)) return;
    setItems((current) => [
      ...current,
      {
        food,
        selection: {
          food_id: food.id,
          grams: food.servings[0]?.grams ?? 100,
          portion_source: "user_estimate",
          uncertainty_percent: 20,
        },
      },
    ]);
  };
  const canSubmit =
    items.length > 0 ||
    description.trim().length > 0 ||
    Boolean(imageId && capabilities?.vision && api.mode === "live");
  const submit = () => {
    if (!canSubmit) return;
    onSubmit({
      image_id: imageId,
      description: description.trim(),
      items: items.map((item) => item.selection),
      meal_name: name.trim() || "My meal",
      meal_type: type,
      language: preferences.language,
      detailed,
      confirmed: items.length > 0,
    });
    onClose();
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="What's on your plate?"
      description="A few details make a more useful estimate."
    >
      {imageId && !capabilities?.vision && (
        <div className="notice">
          <p>
            {api.mode === "demo"
              ? "The demo does not recognize photos."
              : "Your model is text-only."}{" "}
            Add the food names or choose them below.
          </p>
        </div>
      )}
      <div className="form-grid">
        <Field label="Meal name">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={100}
          />
        </Field>
        <Field label="Meal">
          <select
            value={type}
            onChange={(event) => setType(event.target.value as MealType)}
          >
            <option value="breakfast">Breakfast</option>
            <option value="lunch">Lunch</option>
            <option value="dinner">Dinner</option>
            <option value="snack">Snack</option>
          </select>
        </Field>
      </div>
      <Field
        label="Describe the food"
        hint="Include cooking method, sauces and any measured portions."
      >
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
          maxLength={3000}
          placeholder="Rice, yellow dal and a boiled egg…"
        />
      </Field>
      {items.length > 0 && (
        <div className="selected-foods">
          {items.map(({ food, selection }) => (
            <div key={food.id} className="selected-food">
              <span>{food.name}</span>
              <label>
                <input
                  aria-label={`${food.name} grams`}
                  type="number"
                  min="1"
                  max="5000"
                  step="1"
                  value={selection.grams}
                  onChange={(event) => {
                    const grams = Number(event.target.value);
                    setItems((current) =>
                      current.map((item) =>
                        item.food.id === food.id
                          ? { ...item, selection: { ...item.selection, grams } }
                          : item,
                      ),
                    );
                  }}
                />
                <small>g</small>
              </label>
              <IconButton
                label={`Remove ${food.name}`}
                onClick={() =>
                  setItems((current) =>
                    current.filter((item) => item.food.id !== food.id),
                  )
                }
              >
                <Trash2 size={15} />
              </IconButton>
            </div>
          ))}
        </div>
      )}
      <button
        className="text-button add-food"
        onClick={() => setSearchOpen((current) => !current)}
      >
        <Plus size={16} />
        {searchOpen ? "Hide food search" : "Choose exact foods and portions"}
      </button>
      {searchOpen && (
        <FoodSearch
          onSelect={add}
          selected={items.map((item) => item.food.id)}
          compact
        />
      )}
      <Toggle
        checked={detailed}
        onChange={setDetailed}
        label="Detailed review"
        description="Show source checks and assumptions. Supported local models can use a reasoning budget."
      />
      <div className="modal-footer">
        <Button variant="ghost" onClick={onClose}>
          Back
        </Button>
        <Button
          onClick={submit}
          disabled={
            !canSubmit ||
            items.some(
              (item) =>
                !Number.isFinite(item.selection.grams) ||
                item.selection.grams <= 0 ||
                item.selection.grams > 5000,
            )
          }
        >
          Analyse meal
          <ArrowRight size={17} />
        </Button>
      </div>
    </Modal>
  );
}
