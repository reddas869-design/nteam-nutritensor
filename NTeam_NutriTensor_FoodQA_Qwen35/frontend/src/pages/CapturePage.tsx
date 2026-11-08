import { useEffect, useRef, useState } from "react";
import { Camera, ImagePlus, SwitchCamera } from "lucide-react";
import { useCamera } from "../hooks/useCamera";
import { useAnalysis } from "../hooks/useAnalysis";
import { useWorkspace } from "../state/workspace";
import { scanRequest } from "../lib/scan";
import { ScanStatus } from "../components/ScanStatus";
import { ScanResult } from "../components/ScanResult";

export default function CapturePage() {
  const { api, preferences, connected } = useWorkspace();
  const camera = useCamera();
  const analysis = useAnalysis();
  const input = useRef<HTMLInputElement>(null);
  const attempt = useRef(0);
  const uploading = useRef(false);
  const [phase, setPhase] = useState<"camera" | "processing">("camera");
  const [failed, setFailed] = useState(false);
  const [failureReason, setFailureReason] = useState<string | null>(null);
  const [photo, setPhoto] = useState<string | null>(null);
  useEffect(
    () => () => {
      attempt.current += 1;
    },
    [],
  );
  useEffect(
    () => () => {
      if (photo) URL.revokeObjectURL(photo);
    },
    [photo],
  );

  const accept = async (blob: Blob) => {
    if (uploading.current) return;
    uploading.current = true;
    const current = ++attempt.current;
    camera.stop();
    setPhase("processing");
    setFailed(false);
    setFailureReason(null);
    setPhoto(URL.createObjectURL(blob));
    try {
      // Demo mode never pretends to recognize an uploaded photo.
      if (!connected || api.mode !== "live")
        throw new Error("Live vision required");
      const uploaded = await api.upload(blob);
      if (current !== attempt.current) return;
      await analysis.run(scanRequest(uploaded.id, preferences.language));
    } catch (cause) {
      if (current === attempt.current) {
        setFailureReason(cause instanceof Error ? cause.message : null);
        setFailed(true);
      }
    } finally {
      if (current === attempt.current) uploading.current = false;
    }
  };
  const capture = async () => {
    try {
      await accept(await camera.capture());
    } catch (cause) {
      setFailureReason(cause instanceof Error ? cause.message : null);
      setFailed(true);
      setPhase("processing");
    }
  };
  const reset = () => {
    attempt.current += 1;
    uploading.current = false;
    analysis.reset();
    setPhoto(null);
    setFailed(false);
    setFailureReason(null);
    setPhase("camera");
  };
  if (analysis.result && phase === "processing") {
    return (
      <ScanResult
        key={analysis.result.id}
        result={analysis.result}
        photo={photo}
        onBack={reset}
      />
    );
  }
  if (phase === "processing") {
    return <ScanStatus failed={failed || !!analysis.error} reason={analysis.error ?? failureReason} onBack={reset} />;
  }
  return (
    <main className="camera-screen" aria-label="Food camera">
      <video
        ref={camera.video}
        className="camera-feed"
        muted
        playsInline
        aria-label="Camera preview"
      />
      {!camera.active && (
        <div className="camera-start">
          <Camera size={34} strokeWidth={1.15} aria-hidden="true" />
          <h1>About: Models are engineered, not a toy. ntemma is a optimized multimodal model developed from scratch by NTeam to recognize food/fruit only. It took 4+ months to develop and required a strong visual understanding of maths to build its core architecture. Maintaining the server also incurs ongoing electricity costs.</h1>
          <p>{camera.error || "A clear view of your food."}</p>
          <button onClick={() => void camera.start()} disabled={camera.pending}>
            {camera.pending ? "Opening camera…" : "Sir, Open camera"}
          </button>
        </div>
      )}
      <div className="camera-controls">
        <button
          className="camera-control"
          onClick={() => input.current?.click()}
          aria-label="Choose a food photo"
        >
          photo
        </button>
        <button
          className="shutter"
          onClick={() => void capture()}
          disabled={!camera.active}
          aria-label="Capture food photo"
        >
          <span />
        </button>
        <button
          className="camera-control"
          onClick={() => void camera.flip()}
          disabled={!camera.active || camera.pending}
          aria-label="Switch camera"
        >
          switch
        </button>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void accept(file);
          event.target.value = "";
        }}
      />
    </main>
  );
}
