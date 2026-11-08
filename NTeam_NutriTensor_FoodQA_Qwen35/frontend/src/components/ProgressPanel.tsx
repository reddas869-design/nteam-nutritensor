import { Check, Circle, LoaderCircle, X } from "lucide-react";
import { stageLabels } from "../lib/defaults";
import { useWorkspace } from "../state/workspace";
import type { JobEvent, Stage } from "../lib/types";
import { Button } from "./Primitives";

const stages: Stage[] = [
  "identify",
  "retrieve",
  "calculate",
  "review",
  "explain",
];

export function ProgressPanel({
  events,
  onCancel,
}: {
  events: JobEvent[];
  onCancel(): void;
}) {
  const { api } = useWorkspace();
  const latest = events.at(-1);
  return (
    <section
      className="progress-card"
      aria-live="polite"
      aria-label="Analysis progress"
    >
      <div className="progress-orbit">
        <span />
        <span />
        <span />
        <LoaderCircle size={27} className="spin" />
      </div>
      <p className="eyebrow">
        {api.mode === "demo" ? "EXAMPLE WORKFLOW" : "YOUR MEAL, UNDERSTOOD"}
      </p>
      <h2>{latest ? stageLabels[latest.stage] : "Preparing your meal"}</h2>
      <p className="subtle">Following the food from source to serving.</p>
      <div className="progress-track">
        <span style={{ width: `${(latest?.progress ?? 0.05) * 100}%` }} />
      </div>
      <ol className="agent-stages">
        {stages.map((stage) => {
          const completed = events.some(
            (event) => event.stage === stage && event.state === "completed",
          );
          const active = !completed && latest?.stage === stage;
          return (
            <li
              key={stage}
              className={completed ? "completed" : active ? "active" : ""}
            >
              {completed ? (
                <Check size={15} />
              ) : active ? (
                <LoaderCircle size={15} className="spin" />
              ) : (
                <Circle size={10} />
              )}
              <span>{stageLabels[stage]}</span>
            </li>
          );
        })}
      </ol>
      <Button variant="ghost" onClick={onCancel}>
        <X size={15} />
        Cancel analysis
      </Button>
    </section>
  );
}
