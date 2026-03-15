"use client";

import { Shield, ArrowLeft } from "lucide-react";
import Link from "next/link";
import AIProcessingOptOut from "@/components/privacy/AIProcessingOptOut";

export default function ResidentPrivacySettings() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/resident"
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500 transition hover:bg-slate-200"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100">
            <Shield className="h-5 w-5 text-slate-600" />
          </span>
          <div>
            <h1 className="text-lg font-bold text-slate-800">
              Privacy Settings
            </h1>
            <p className="text-xs text-slate-500">
              Control how your data is processed and stored
            </p>
          </div>
        </div>
      </div>

      {/* AI Processing Opt-Out */}
      <AIProcessingOptOut
        initialOptOut={false}
        onUpdate={(optOut) => {
          console.log("AI Opt-Out updated:", optOut);
        }}
      />

      {/* Additional privacy info */}
      <div className="rounded-xl bg-slate-50 px-6 py-5 ring-1 ring-slate-100">
        <h3 className="text-sm font-semibold text-slate-800 mb-2">
          About AI Processing
        </h3>
        <div className="space-y-2 text-xs text-slate-600">
          <p>
            When a Service Pro completes a job at your property, they submit a
            verification photo or video. By default, this media is analyzed by
            Cloudflare Workers AI to check cleanliness quality.
          </p>
          <p>
            Before any analysis, our privacy detection system automatically
            scans for faces, family photos, and sensitive documents visible in
            the frame. Blur metadata is applied to protect your privacy before
            the image is stored.
          </p>
          <p>
            If you prefer no AI involvement at all, enable the opt-out toggle
            above. A human QA Inspector will review the media manually instead.
          </p>
        </div>
      </div>
    </div>
  );
}
