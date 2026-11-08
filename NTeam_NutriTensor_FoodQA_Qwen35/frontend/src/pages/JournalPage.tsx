import { useMemo, useState } from "react";
import {
  ArrowDownToLine,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { useAsync } from "../hooks/useAsync";
import { downloadBlob, errorMessage } from "../lib/export";
import {
  formatEnergy,
  formatNutrient,
  localDay,
  sumNutrients,
} from "../lib/nutrition";
import type { JournalEntry, MealType } from "../lib/types";
import {
  Badge,
  Button,
  EmptyState,
  ErrorNotice,
  Field,
  IconButton,
  Loading,
  Modal,
  PageHeading,
} from "../components/Primitives";
import { ResultPanel } from "../components/ResultPanel";

export default function JournalPage() {
  const { api, revision, changed, setPage, toast, preferences } =
    useWorkspace();
  const { data, loading, error, reload } = useAsync(
    () => api.journal(),
    [api, revision],
  );
  const [search, setSearch] = useState("");
  const [type, setType] = useState<MealType | "all">("all");
  const [selected, setSelected] = useState<JournalEntry | null>(null);
  const [editing, setEditing] = useState<JournalEntry | null>(null);
  const [deleting, setDeleting] = useState<JournalEntry | null>(null);
  const [pending, setPending] = useState(false);
  const filtered = useMemo(
    () =>
      (data ?? []).filter(
        (entry) =>
          (type === "all" || entry.meal_type === type) &&
          entry.meal_name
            .toLocaleLowerCase()
            .includes(search.toLocaleLowerCase()),
      ),
    [data, type, search],
  );
  const groups = useMemo(() => {
    const result = new Map<string, JournalEntry[]>();
    for (const entry of filtered) {
      const day = localDay(entry.eaten_at, preferences.timezone);
      result.set(day, [...(result.get(day) ?? []), entry]);
    }
    return [...result.entries()].sort(([left], [right]) =>
      right.localeCompare(left),
    );
  }, [filtered, preferences.timezone]);
  const exportMeals = async () => {
    try {
      downloadBlob(await api.exportData("csv"), "nutritensor-meals.csv");
      toast("Meal export downloaded", "success");
    } catch (cause) {
      toast(errorMessage(cause), "error");
    }
  };
  const remove = async () => {
    if (!deleting) return;
    setPending(true);
    try {
      await api.deleteMeal(deleting.id);
      setDeleting(null);
      changed();
      toast("Meal removed from your journal");
    } catch (cause) {
      toast(errorMessage(cause), "error");
    } finally {
      setPending(false);
    }
  };
  const saveEdit = async () => {
    if (!editing) return;
    setPending(true);
    try {
      await api.editMeal(editing.id, {
        meal_name: editing.meal_name,
        meal_type: editing.meal_type,
        notes: editing.notes,
      });
      setEditing(null);
      changed();
      toast("Meal details updated", "success");
    } catch (cause) {
      toast(errorMessage(cause), "error");
    } finally {
      setPending(false);
    }
  };
  return (
    <main className="workspace-page journal-page">
      <PageHeading
        eyebrow="OUR FOOD STORY"
        title="THE MEAL HOUSE."
        text="A place for the meals you've taken a moment to understand."
        action={
          <Button onClick={() => setPage("capture")}>
            <Plus size={17} />
            Add a meal
          </Button>
        }
      />
      <div className="journal-toolbar">
        {/* <label className="search-input">
          <Search size={17} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Find a meal…"
            aria-label="Search saved meals"
          />
        </label> */}
        <select
          value={type}
          onChange={(event) => setType(event.target.value as MealType | "all")}
          aria-label="Filter meal type"
        >
          <option value="all">All meals</option>
          <option value="breakfast">Breakfast</option>
          <option value="lunch">Lunch</option>
          <option value="dinner">Dinner</option>
          <option value="snack">Snacks</option>
        </select>
        <Button variant="secondary" onClick={() => void exportMeals()}>
          <ArrowDownToLine size={16} />
          Export
        </Button>
      </div>
      {loading && <Loading />}
      {error && <ErrorNotice message={error} retry={() => void reload()} />}
      {!loading && !error && !filtered.length && (
        <EmptyState
          icon={<BookOpen size={32} />}
          title={
            data?.length
              ? "No matching meals"
              : "Your next meal starts the story."
          }
          text={
            data?.length
              ? "Try another search or meal filter."
              : "Analyse a meal, confirm the foods and portions, then save it here."
          }
          action="Discover a meal"
          onAction={() => setPage("capture")}
        />
      )}
      <div className="journal-groups">
        {groups.map(([day, entries]) => {
          const totals = sumNutrients(
            entries.map((entry) => entry.result.totals),
          );
          return (
            <section key={day} className="journal-day">
              {/* <div className="journal-day-heading">
                <h2>
                  <CalendarDays size={17} />
                  {new Date(`${day}T12:00:00`).toLocaleDateString("en-IN", {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                  })}
                </h2>
                <span>
                  {entries.length} {entries.length === 1 ? "meal" : "meals"} ·{" "}
                  {formatEnergy(totals.energy_kcal)} kcal logged
                </span>
              </div> */}
              <div className="journal-cards">
                {entries.map((entry) => (
                  <article className="journal-card" key={entry.id}>
                    <div
                      className={`meal-art meal-art-${entry.meal_type}`}
                      aria-hidden="true"
                    >
                      <div className="mini-plate">
                        <span />
                        <span />
                        <span />
                      </div>
                      <small>{entry.meal_type}</small>
                    </div>
                    <div className="journal-card-content">
                      <div className="journal-card-meta">
                        <Badge>{entry.meal_type}</Badge>
                        <span>
                          {new Date(entry.eaten_at).toLocaleTimeString(
                            "en-IN",
                            {
                              timeZone: preferences.timezone,
                              hour: "numeric",
                              minute: "2-digit",
                            },
                          )}
                        </span>
                      </div>
                      <button
                        className="journal-card-title"
                        onClick={() => setSelected(entry)}
                      >
                        <h3>{entry.meal_name}</h3>
                        <ArrowUpRight size={17} />
                      </button>
                      <p>
                        {entry.result.portions
                          .map((portion) => portion.food.name)
                          .join(" · ")}
                      </p>
                      <div className="journal-card-nutrients">
                        <strong>
                          {formatEnergy(entry.result.totals.energy_kcal)}{" "}
                          <small>kcal</small>
                        </strong>
                        <span>
                          {formatNutrient(entry.result.totals.protein_g)} g
                          protein
                        </span>
                      </div>
                      <div className="journal-card-actions">
                        <button
                          className="text-button"
                          onClick={() => setEditing(entry)}
                        >
                          Edit details
                        </button>
                        <IconButton
                          label={`Delete ${entry.meal_name}`}
                          onClick={() => setDeleting(entry)}
                        >
                          <Trash2 size={15} />
                        </IconButton>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          );
        })}
      </div>
      {selected && (
        <div className="saved-result-overlay">
          <button
            className="panel-backdrop"
            onClick={() => setSelected(null)}
            aria-label="Close saved analysis"
          />
          <ResultPanel
            result={selected.result}
            onClose={() => setSelected(null)}
            onRecalculate={() => undefined}
            readOnly
          />
        </div>
      )}
      <Modal
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Remove this meal?"
        description="This removes the journal entry. Your original analysis remains in the workspace."
      >
        <div className="modal-footer">
          <Button variant="ghost" onClick={() => setDeleting(null)}>
            Keep meal
          </Button>
          <Button
            variant="danger"
            loading={pending}
            onClick={() => void remove()}
          >
            Remove meal
          </Button>
        </div>
      </Modal>
      <Modal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title="meal details"
      >
        {editing && (
          <>
            <Field label="Meal name">
              <input
                value={editing.meal_name}
                maxLength={100}
                onChange={(event) =>
                  setEditing({ ...editing, meal_name: event.target.value })
                }
              />
            </Field>
            <Field label="Meal type">
              <select
                value={editing.meal_type}
                onChange={(event) =>
                  setEditing({
                    ...editing,
                    meal_type: event.target.value as MealType,
                  })
                }
              >
                <option value="breakfast">Breakfast</option>
                <option value="lunch">Lunch</option>
                <option value="dinner">Dinner</option>
                <option value="snack">Snack</option>
              </select>
            </Field>
            {/* <Field label="Notes">
              <textarea
                value={editing.notes}
                maxLength={3000}
                rows={3}
                onChange={(event) =>
                  setEditing({ ...editing, notes: event.target.value })
                }
                placeholder="What would you like to remember?"
              />
            </Field> */}
            <div className="modal-footer">
              <Button
                onClick={() => void saveEdit()}
                loading={pending}
                disabled={!editing.meal_name.trim()}
              >
                Save details
              </Button>
            </div>
          </>
        )}
      </Modal>
    </main>
  );
}
