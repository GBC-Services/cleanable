"use client";

import { useCallback, useRef, useState } from "react";
import {
  Camera,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Video,
  Image as ImageIcon,
  X,
  Eye,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";

// ── Types ──────────────────────────────────────────────────────────────

interface VerificationResult {
  id: number;
  uuid: string;
  status: number;
  status_display: string;
  cleanliness_score: number | null;
  ai_summary: string | null;
  issues_detected: string[] | null;
}

interface VideoUploadProps {
  bookingId: number;
  bookingUuid?: string;
  onSuccess?: (result: VerificationResult) => void;
}

type UploadState = "idle" | "preview" | "uploading" | "analyzing" | "done" | "error";

// ── Helpers ────────────────────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 0.85) return "text-green-600";
  if (score >= 0.60) return "text-amber-600";
  return "text-red-600";
}

function scoreBg(score: number): string {
  if (score >= 0.85) return "bg-green-50";
  if (score >= 0.60) return "bg-amber-50";
  return "bg-red-50";
}

function scoreLabel(score: number): string {
  if (score >= 0.85) return "Excellent";
  if (score >= 0.70) return "Good";
  if (score >= 0.60) return "Needs Review";
  return "Below Standard";
}

// ── Component ──────────────────────────────────────────────────────────

export default function VideoUpload({
  bookingId,
  bookingUuid,
  onSuccess,
}: VideoUploadProps) {
  const { tokens } = useAuthStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [state, setState] = useState<UploadState>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<"image" | "video">("image");
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

  // ── File Selection ─────────────────────────────────────────────────

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    // Validate file type
    const isImage = selected.type.startsWith("image/");
    const isVideo = selected.type.startsWith("video/");
    if (!isImage && !isVideo) {
      setError("Please select an image or video file.");
      return;
    }

    // Validate size (50MB max)
    if (selected.size > 50 * 1024 * 1024) {
      setError("File size must be under 50 MB.");
      return;
    }

    setFile(selected);
    setMediaType(isVideo ? "video" : "image");
    setError(null);

    // Generate preview
    const url = URL.createObjectURL(selected);
    setPreview(url);
    setState("preview");
  }, []);

  // ── Upload ─────────────────────────────────────────────────────────

  const handleUpload = async () => {
    if (!file || !tokens?.access) return;

    setState("uploading");
    setError(null);

    const formData = new FormData();
    formData.append("booking", String(bookingId));
    formData.append("media_file", file);
    formData.append("media_type", mediaType);

    try {
      const res = await fetch(`${API_BASE}/api/v1/support/verify/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokens.access}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(
          errBody.detail || errBody.media_file?.[0] || "Upload failed.",
        );
      }

      const data = await res.json();
      setState("analyzing");

      // Poll for analysis result
      pollForResult(data.id || data.uuid);
    } catch (err: unknown) {
      setState("error");
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  };

  // ── Poll for Analysis ──────────────────────────────────────────────

  const pollForResult = async (idOrUuid: string | number) => {
    const endpoint = `${API_BASE}/api/v1/support/verify/${idOrUuid}/`;
    let attempts = 0;
    const maxAttempts = 30; // 60 seconds max

    const poll = async () => {
      attempts++;
      if (attempts > maxAttempts) {
        setState("done");
        setResult({
          id: 0,
          uuid: String(idOrUuid),
          status: 20,
          status_display: "Analyzing",
          cleanliness_score: null,
          ai_summary: "Analysis is still running. Check back shortly.",
          issues_detected: null,
        });
        return;
      }

      try {
        const res = await fetch(endpoint, {
          headers: {
            Authorization: `Bearer ${tokens?.access}`,
          },
        });

        if (res.ok) {
          const data = await res.json();
          // Status 20 = still analyzing
          if (data.status === 20 || data.status === 10) {
            setTimeout(poll, 2000);
            return;
          }

          setState("done");
          setResult(data);
          onSuccess?.(data);
          return;
        }
      } catch {
        // Retry on network error
      }

      setTimeout(poll, 2000);
    };

    poll();
  };

  // ── Reset ──────────────────────────────────────────────────────────

  const handleReset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setState("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-50">
            <Camera className="h-5 w-5 text-indigo-600" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-slate-800">
              Post-Job Verification
            </h2>
            <p className="text-xs text-slate-500">
              Upload a photo or video for AI cleanliness review
            </p>
          </div>
        </div>
        {state !== "idle" && state !== "uploading" && state !== "analyzing" && (
          <button
            data-testid="button-reset-upload"
            onClick={handleReset}
            className="text-xs text-slate-400 hover:text-slate-600 transition"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="px-6 py-5 space-y-4">
        {/* Idle — File picker */}
        {state === "idle" && (
          <div
            data-testid="dropzone-verification"
            onClick={() => fileInputRef.current?.click()}
            className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 px-6 py-10 cursor-pointer transition hover:border-indigo-300 hover:bg-indigo-50/30"
          >
            <Upload className="h-8 w-8 text-slate-400 mb-3" />
            <p className="text-sm font-medium text-slate-600">
              Tap to upload a photo or video
            </p>
            <p className="mt-1 text-xs text-slate-400">
              JPG, PNG, MP4 up to 50 MB
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,video/*"
              capture="environment"
              onChange={handleFileSelect}
              className="hidden"
              data-testid="input-file-upload"
            />
          </div>
        )}

        {/* Preview */}
        {state === "preview" && preview && (
          <div className="space-y-4">
            <div className="relative rounded-lg overflow-hidden bg-black">
              {mediaType === "video" ? (
                <video
                  src={preview}
                  controls
                  className="w-full max-h-64 object-contain"
                  data-testid="video-preview"
                />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={preview}
                  alt="Verification preview"
                  className="w-full max-h-64 object-contain"
                  data-testid="image-preview"
                />
              )}
              <span className="absolute top-2 right-2 inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-1 text-xs text-white">
                {mediaType === "video" ? (
                  <Video className="h-3 w-3" />
                ) : (
                  <ImageIcon className="h-3 w-3" />
                )}
                {file?.name}
              </span>
            </div>

            <div className="flex gap-3">
              <button
                data-testid="button-submit-verification"
                onClick={handleUpload}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700"
              >
                <Upload className="h-4 w-4" />
                Submit for AI Review
              </button>
              <button
                data-testid="button-cancel-upload"
                onClick={handleReset}
                className="rounded-lg bg-slate-100 px-4 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-200"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Uploading */}
        {state === "uploading" && (
          <div className="flex flex-col items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500 mb-3" />
            <p className="text-sm font-medium text-slate-600">Uploading...</p>
            <p className="text-xs text-slate-400 mt-1">
              Sending media to the server
            </p>
          </div>
        )}

        {/* Analyzing */}
        {state === "analyzing" && (
          <div className="flex flex-col items-center justify-center py-8">
            <div className="relative mb-3">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
              <Eye className="absolute inset-0 m-auto h-4 w-4 text-indigo-600" />
            </div>
            <p className="text-sm font-medium text-slate-600">
              AI is analyzing your submission...
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Cloudflare Workers AI vision model is reviewing the room
            </p>
          </div>
        )}

        {/* Done — Show result */}
        {state === "done" && result && (
          <div className="space-y-4">
            {/* Score badge */}
            {result.cleanliness_score !== null && (
              <div
                className={`flex items-center gap-4 rounded-lg p-4 ${scoreBg(result.cleanliness_score)}`}
              >
                <div className="text-center">
                  <p
                    className={`text-3xl font-bold ${scoreColor(result.cleanliness_score)}`}
                  >
                    {Math.round(result.cleanliness_score * 100)}%
                  </p>
                  <p
                    className={`text-xs font-medium ${scoreColor(result.cleanliness_score)}`}
                  >
                    {scoreLabel(result.cleanliness_score)}
                  </p>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    {result.cleanliness_score >= 0.85 ? (
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-amber-600" />
                    )}
                    <span className="text-sm font-semibold text-slate-800">
                      {result.status_display}
                    </span>
                  </div>
                  {result.ai_summary && (
                    <p className="text-xs text-slate-600">
                      {result.ai_summary}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Issues */}
            {result.issues_detected && result.issues_detected.length > 0 && (
              <div className="rounded-lg bg-amber-50 p-4">
                <p className="text-xs font-semibold text-amber-800 mb-2">
                  Issues Detected
                </p>
                <ul className="space-y-1">
                  {result.issues_detected.map((issue, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-xs text-amber-700"
                    >
                      <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Upload another */}
            <button
              data-testid="button-upload-another"
              onClick={handleReset}
              className="w-full rounded-lg bg-slate-100 px-4 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-200"
            >
              Upload Another
            </button>
          </div>
        )}

        {/* Error */}
        {state === "error" && error && (
          <div className="space-y-3">
            <div className="flex items-start gap-3 rounded-lg bg-red-50 p-4">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
            <button
              data-testid="button-retry-upload"
              onClick={handleReset}
              className="w-full rounded-lg bg-slate-100 px-4 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-200"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
