import { ArrowLeft, RotateCcw } from "lucide-react";
import { RETRY_MESSAGE } from "../lib/scan";

export function ScanStatus({
  failed,
  reason,
  onBack,
}: {
  failed?: boolean;
  reason?: string | null;
  onBack(): void;
}) {
  return (
    <main
      className="scan-stage scan-status"
      aria-live="polite"
      aria-busy={!failed}
    >
      <div
        className={`scan-orbit ${failed ? "scan-orbit-error" : ""}`}
        aria-hidden="true"
      >
        {failed ? (
          <RotateCcw size={34} strokeWidth={1.3} />
        ) : (
          <>
            <i />
            <i />
            <i />
          </>
        )}
      </div>
      <h1>{failed ? RETRY_MESSAGE : "sir, plz wait, performing high-dimensional tensor operation..."}</h1>
      <p>
        {failed
          ? reason && reason !== RETRY_MESSAGE
            ? reason
            : "Try a clear, well-lit photo of recognizable food or only foods are recognizable."
          : "Finding the food and its nutrition."}
      </p>
      <h3>Every contribution helps advance our little project</h3>

          
      <button className="scan-secondary" onClick={onBack}>
        {failed ? <RotateCcw size={17} /> : <ArrowLeft size={17} />}
        {failed ? "Try again sir" : "Cancel"}
      </button>
      <h4>[Donate PLZ]</h4>
    </main>
  );
}
