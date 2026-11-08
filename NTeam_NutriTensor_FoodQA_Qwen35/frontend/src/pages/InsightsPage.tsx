import { useMemo, useState } from "react";
import {
  ArrowUpRight,
  CalendarRange,
  ChartNoAxesColumnIncreasing,
} from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { useAsync } from "../hooks/useAsync";
import {
  formatEnergy,
  formatNutrient,
  localDay,
  NUTRIENTS,
} from "../lib/nutrition";
import type { NutrientKey, Summary } from "../lib/types";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageHeading,
} from "../components/Primitives";

function period(
  days: number,
  timezone: string,
): { start: string; end: string } {
  const end = localDay(new Date().toISOString(), timezone);
  const beginning = new Date(`${end}T12:00:00Z`);
  beginning.setUTCDate(beginning.getUTCDate() - days + 1);
  return { start: beginning.toISOString().slice(0, 10), end };
}

export default function InsightsPage() {
  const { api, preferences, revision, setPage } = useWorkspace();
  const [days, setDays] = useState(7);
  const [metric, setMetric] = useState<NutrientKey>("energy_kcal");
  const range = useMemo(
    () => period(days, preferences.timezone),
    [days, preferences.timezone],
  );
  const { data, loading, error, reload } = useAsync(
    () => api.summary(range.start, range.end),
    [api, range.start, range.end, revision],
  );
  const selectedMetric = NUTRIENTS.find((item) => item.key === metric)!;
  return (
    <main className="workspace-page insights-page">
      <PageHeading
        eyebrow="STEP BACK, SEE MORE"
        title="A wider view."
        text="Patterns in the meals you logged. A little perspective, without the pressure."
        action={
          <div className="period-switch">
            {[7, 14, 30].map((value) => (
              <button
                className={days === value ? "active" : ""}
                key={value}
                onClick={() => setDays(value)}
              >
                {value} days
              </button>
            ))}
          </div>
        }
      />
      {loading && <Loading label="Reading your meal journal" />}
      {error && <ErrorNotice message={error} retry={() => void reload()} />}
      {!loading && data && data.meal_count === 0 && (
        <EmptyState
          icon={<ChartNoAxesColumnIncreasing size={34} />}
          title="A little history goes a long way."
          text="Save a few meals to our most powerful SLM freely"
          action="Add your first meal"
          onAction={() => setPage("capture")}
        />
      )}
      {!loading && data && data.meal_count > 0 && (
        <>
          <div className="insight-stats">
            <div>
              <p>Meals explored</p>
              <strong>{data.meal_count}</strong>
              <span>across {data.recorded_days} recorded days</span>
            </div>
            <div>
              <p>Energy logged</p>
              <strong>
                {formatEnergy(data.totals.energy_kcal)}
                <small>kcal</small>
              </strong>
              <span>sum of recorded meals</span>
            </div>
            <div>
              <p>Protein logged</p>
              <strong>
                {formatNutrient(data.totals.protein_g, 0)}
                <small>g</small>
              </strong>
              <span>source values × portions</span>
            </div>
          </div>
          <section className="chart-card">
            <div className="chart-heading">
              <div>
                <p className="eyebrow">ONE DAY AT A TIME</p>
                <h2>Your logged {selectedMetric.label.toLowerCase()}</h2>
              </div>
              <select
                aria-label="Chart nutrient"
                value={metric}
                onChange={(event) =>
                  setMetric(event.target.value as NutrientKey)
                }
              >
                {NUTRIENTS.map((item) => (
                  <option value={item.key} key={item.key}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <DayChart
              summary={data}
              metric={metric}
              color={selectedMetric.color}
              unit={selectedMetric.unit}
            />
            <div className="chart-legend">
              <span>
                <i style={{ background: selectedMetric.color }} />
                Logged total
              </span>
              <span>
                <i className="unlogged-key" />
                No logged data
              </span>
              <Badge>{preferences.timezone}</Badge>
            </div>
            <p className="fine-print">
              {data.note} Unknown nutrient values are gaps, not zero.
            </p>
          </section>
          <div className="insight-bottom">
            <section className="insight-note">
              <CalendarRange size={26} />
              <h3>Curiosity over perfection.</h3>
              <p>
                A journal shows what you recorded. Use questionsQ about that food
                if Q is about outside that food. you will get an error. stay carefull.
              </p>
            </section>
            <section className="insight-note pale">
              <h3>See what went into the numbers.</h3>
              <p>
                Each meal keeps its portion weights, source records and
                assumptions for you to revisit.
              </p>
              <button
                className="text-button"
                onClick={() => setPage("journal")}
              >
                Open your journal
                <ArrowUpRight size={16} />
              </button>
            </section>
          </div>
        </>
      )}
    </main>
  );
}

function DayChart({
  summary,
  metric,
  color,
  unit,
}: {
  summary: Summary;
  metric: NutrientKey;
  color: string;
  unit: string;
}) {
  const [focused, setFocused] = useState<number | null>(null);
  const maximum = Math.max(
    1,
    ...summary.days.map((day) => day.totals[metric] ?? 0),
  );
  const ceiling = Math.ceil(maximum / 5) * 5;
  const item = focused === null ? null : summary.days[focused];
  return (
    <div className="day-chart">
      <div className="chart-axis">
        <span>{formatNutrient(ceiling, 0)}</span>
        <span>{formatNutrient(ceiling / 2, 0)}</span>
        <span>0 {unit}</span>
      </div>
      <div className="chart-plot">
        <div className="chart-grid-lines" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div className="chart-columns">
          {summary.days.map((day, index) => {
            const value = day.totals[metric];
            const date = new Date(`${day.date}T12:00:00Z`);
            const known = value !== null;
            return (
              <button
                key={day.date}
                className={`chart-column ${focused === index ? "focused" : ""}`}
                onMouseEnter={() => setFocused(index)}
                onMouseLeave={() => setFocused(null)}
                onFocus={() => setFocused(index)}
                onBlur={() => setFocused(null)}
                aria-label={`${day.date}: ${known ? `${formatNutrient(value)} ${unit}, ${day.meal_count} meals logged` : "No known total"}`}
              >
                <span className="chart-bar-container">
                  {known ? (
                    <span
                      className="chart-bar"
                      style={{
                        height: `${Math.max(1, (value / ceiling) * 100)}%`,
                        background: color,
                      }}
                    />
                  ) : (
                    <span className="chart-bar-empty" />
                  )}
                </span>
                <span className="chart-date">
                  {summary.days.length <= 14
                    ? date
                        .toLocaleDateString("en", { weekday: "short" })
                        .slice(0, 1)
                    : index % 5 === 0
                      ? date.getUTCDate()
                      : ""}
                </span>
              </button>
            );
          })}
        </div>
        {item && (
          <div className="chart-tooltip" role="status">
            <strong>{item.date}</strong>
            <span>
              {formatNutrient(item.totals[metric])} {unit}
            </span>
            <small>{item.meal_count} meals logged</small>
          </div>
        )}
      </div>
    </div>
  );
}
