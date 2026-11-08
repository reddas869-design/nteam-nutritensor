import { useCallback, useEffect, useRef, useState } from "react";

export function useCamera() {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const generation = useRef(0);
  const [active, setActive] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [resolution, setResolution] = useState("");

  const stop = useCallback(() => {
    generation.current += 1;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    setActive(false);
    setPending(false);
  }, []);

  const start = useCallback(
    async (direction: "environment" | "user" = facing) => {
      stop();
      setError(null);
      setPending(true);
      const current = generation.current;
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error(
            "Camera access requires HTTPS or localhost. You can still upload a photo.",
          );
        }
        const next = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: direction },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        });
        if (current !== generation.current) {
          next.getTracks().forEach((track) => track.stop());
          return;
        }
        stream.current = next;
        if (video.current) {
          video.current.srcObject = next;
          await video.current.play();
        }
        const settings = next.getVideoTracks()[0]?.getSettings();
        setResolution(
          settings?.width
            ? `${settings.width} × ${settings.height}`
            : "Camera ready",
        );
        setFacing(direction);
        setActive(true);
      } catch (cause) {
        if (current !== generation.current) return;
        const named = cause instanceof DOMException ? cause.name : "";
        const message =
          named === "NotAllowedError"
            ? "Camera permission was declined. Enable it in your browser or upload a photo."
            : named === "NotFoundError"
              ? "No camera was found. Upload a photo or describe your meal."
              : cause instanceof Error
                ? cause.message
                : "Could not start the camera.";
        setError(message);
        stream.current?.getTracks().forEach((track) => track.stop());
        stream.current = null;
      } finally {
        if (current === generation.current) setPending(false);
      }
    },
    [facing, stop],
  );

  const capture = useCallback(async (): Promise<Blob> => {
    const element = video.current;
    if (!element || !element.videoWidth || !active)
      throw new Error("Wait for the camera to be ready");
    const maximum = 1600;
    const factor = Math.min(
      1,
      maximum / Math.max(element.videoWidth, element.videoHeight),
    );
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(element.videoWidth * factor);
    canvas.height = Math.round(element.videoHeight * factor);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Could not capture this frame");
    context.drawImage(element, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve, reject) =>
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error("Capture failed"))),
        "image/jpeg",
        0.9,
      ),
    );
  }, [active]);

  const flip = useCallback(
    () => start(facing === "environment" ? "user" : "environment"),
    [facing, start],
  );

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) stop();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      generation.current += 1;
      stream.current?.getTracks().forEach((track) => track.stop());
    };
  }, [stop]);

  return {
    video,
    active,
    pending,
    error,
    facing,
    resolution,
    start,
    stop,
    capture,
    flip,
  };
}
