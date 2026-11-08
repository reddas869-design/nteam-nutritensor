import { useState } from "react";
import { FileText, ScanText } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { errorMessage } from "../lib/export";
import type { LabelResult } from "../lib/types";
import { Button, ErrorNotice, Field, Modal } from "./Primitives";
import { NutrientTable } from "./MacroDisplay";

export function LabelReader({
  open,
  onClose,
  imageId,
}: {
  open: boolean;
  onClose(): void;
  imageId?: string;
}) {
  const { api } = useWorkspace();
  const [text, setText] = useState("");
  const [result, setResult] = useState<LabelResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const parse = async () => {
    setPending(true);
    setError(null);
    try {
      setResult(await api.parseLabel(text));
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  };
  const ocr = async () => {
    if (!imageId) return;
    setPending(true);
    setError(null);
    try {
      const response = await api.imageLabel(imageId);
      if (response.text) setText(response.text);
      setResult(response);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Read a nutrition label"
      description="Extract the numbers, then verify them against the package."
    >
      {imageId && (
        <Button
          variant="secondary"
          loading={pending}
          onClick={() => void ocr()}
        >
          <ScanText size={16} />
          Read uploaded label
        </Button>
      )}
      <Field
        label="Label text"
        hint="Keep units and the per-serving or per-100-g heading."
      >
        <textarea
          rows={6}
          value={text}
          maxLength={10000}
          onChange={(event) => setText(event.target.value)}
          placeholder={
            "Per 100 g\nEnergy 120 kcal\nProtein 6 g\nCarbohydrate 18 g\nFat 3 g\nSodium 120 mg"
          }
        />
      </Field>
      {error && <ErrorNotice message={error} />}
      {result && (
        <div className="label-result">
          {result.message && <p>{result.message}</p>}
          {result.nutrients && (
            <>
              <p className="eyebrow">BASIS: {result.basis ?? "UNKNOWN"}</p>
              <NutrientTable nutrients={result.nutrients} />
              <div className="notice notice-amber">
                <p>{result.warning}</p>
              </div>
            </>
          )}
        </div>
      )}
      <div className="modal-footer">
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
        <Button
          disabled={!text.trim()}
          loading={pending}
          onClick={() => void parse()}
        >
          <FileText size={16} />
          Extract numbers
        </Button>
      </div>
    </Modal>
  );
}
