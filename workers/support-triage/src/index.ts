/**
 * Cloudflare Worker — Support Triage, Spatial Verification & Privacy Detection
 * ==============================================================================
 *
 * Three AI pipelines in one Worker:
 *
 * 1. **Ticket Triage** (`/triage`)
 *    - Sentiment analysis via @cf/huggingface/distilbert-sst-2-int8
 *    - Category classification, summary, and suggested response
 *      via @cf/meta/llama-3.2-3b-instruct
 *    - Priority auto-assignment based on sentiment + category
 *    - Calls back to Django via callback_url
 *
 * 2. **Spatial Verification** (`/verify`)
 *    - Vision analysis via @cf/llava-hf/llava-1.5-7b-hf (LLaVA)
 *    - Analyzes post-job photos for cleanliness, issues, score
 *    - Calls back to Django with results
 *
 * 3. **Privacy Detection** (`/verify-privacy`)
 *    - Pre-storage privacy scan via LLaVA vision model
 *    - Detects human faces, family photos, sensitive documents
 *    - Returns blur metadata regions before R2 storage
 *    - Follows with cleanliness verification (combined pipeline)
 *
 * Authentication: Bearer token (CLEANABLE_API_KEY secret)
 */

// ── Types ──────────────────────────────────────────────────────────────

interface Env {
  AI: Ai;
  CLEANABLE_API_KEY: string;
  ENVIRONMENT: string;
  VERIFICATION_MEDIA: R2Bucket;
}

interface TriageRequest {
  ticket_id: number;
  subject: string;
  text: string;
  user_role: string;
  booking_id: number | null;
  callback_url: string;
}

interface VerifyRequest {
  verification_id: number;
  booking_id: number;
  media_type: "image" | "video";
  image_base64: string;
  callback_url: string;
}

interface PrivacyVerifyRequest {
  verification_id: number;
  booking_id: number;
  media_type: "image" | "video";
  image_base64: string;
  callback_url: string;
  resident_id: number;
  store_to_r2: boolean;
}

interface SentimentResult {
  label: string;
  score: number;
}

interface TriageResult {
  ticket_id: number;
  sentiment: "positive" | "negative" | "neutral";
  sentiment_score: number;
  priority: number;
  ai_category: string;
  ai_summary: string;
  ai_suggested_response: string;
}

interface VerifyResult {
  verification_id: number;
  cleanliness_score: number;
  ai_analysis: Record<string, unknown>;
  ai_summary: string;
  issues_detected: string[];
}

interface PrivacyDetection {
  has_faces: boolean;
  has_family_photos: boolean;
  has_sensitive_documents: boolean;
  detected_items: string[];
  privacy_risk_score: number;
  blur_regions: BlurRegion[];
}

interface BlurRegion {
  type: "face" | "photo" | "document";
  description: string;
  confidence: number;
}

interface PrivacyVerifyResult {
  verification_id: number;
  privacy_detection: PrivacyDetection;
  cleanliness_score: number;
  ai_analysis: Record<string, unknown>;
  ai_summary: string;
  issues_detected: string[];
  r2_key: string | null;
  privacy_scrubbed: boolean;
}

// ── Auth Helper ────────────────────────────────────────────────────────

function validateAuth(request: Request, env: Env): Response | null {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader || authHeader !== `Bearer ${env.CLEANABLE_API_KEY}`) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }
  return null;
}

// ── Sentiment Analysis ─────────────────────────────────────────────────

async function analyzeSentiment(
  ai: Ai,
  text: string,
): Promise<{ sentiment: "positive" | "negative" | "neutral"; score: number }> {
  try {
    const response: any = await ai.run(
      "@cf/huggingface/distilbert-sst-2-int8" as any,
      { text },
    );

    // The model returns an array of { label, score } objects
    const results: SentimentResult[] = Array.isArray(response)
      ? response
      : response?.result ?? response?.data ?? [];

    if (results.length === 0) {
      return { sentiment: "neutral", score: 0.5 };
    }

    // Find the highest-scoring sentiment
    const sorted = [...results].sort((a, b) => b.score - a.score);
    const top = sorted[0];

    const label = top.label.toLowerCase();
    let sentiment: "positive" | "negative" | "neutral";

    if (label.includes("positive") || label === "positive") {
      sentiment = "positive";
    } else if (label.includes("negative") || label === "negative") {
      sentiment = "negative";
    } else {
      sentiment = "neutral";
    }

    return {
      sentiment,
      score: Math.round(top.score * 1000) / 1000,
    };
  } catch (err) {
    console.error("Sentiment analysis failed:", err);
    return { sentiment: "neutral", score: 0.5 };
  }
}

// ── LLM Triage (Category + Summary + Response) ────────────────────────

async function runTriageLLM(
  ai: Ai,
  subject: string,
  text: string,
  sentiment: string,
  userRole: string,
): Promise<{
  ai_category: string;
  ai_summary: string;
  ai_suggested_response: string;
}> {
  const prompt = `You are a support triage assistant for Cleanable, a professional cleaning platform. Analyze the support ticket below and output ONLY valid JSON with three fields.

## Ticket
Subject: ${subject}
Message: ${text}
User Role: ${userRole}
Detected Sentiment: ${sentiment}

## Instructions
Classify and respond:

1. "category": One of: "billing", "scheduling", "quality", "access", "cancellation", "technical", "feedback", "other"
2. "summary": A 1-2 sentence summary of the ticket for the support agent.
3. "suggested_response": A professional, empathetic response to send to the customer (2-3 sentences max).

Output ONLY valid JSON. No markdown, no code fences, no explanation.

JSON:`;

  try {
    const response: any = await ai.run("@cf/meta/llama-3.2-3b-instruct", {
      messages: [
        {
          role: "system",
          content:
            "You are a JSON-only response bot for a cleaning platform support system. Output valid JSON only.",
        },
        { role: "user", content: prompt },
      ],
      max_tokens: 512,
      temperature: 0.2,
      top_p: 0.9,
    });

    const responseText =
      typeof response === "string"
        ? response
        : response?.response ?? response?.result ?? "";

    // Extract JSON
    let jsonStr = responseText.trim();
    const fenceMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (fenceMatch) {
      jsonStr = fenceMatch[1].trim();
    }

    const startIdx = jsonStr.indexOf("{");
    const endIdx = jsonStr.lastIndexOf("}");
    if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
      jsonStr = jsonStr.slice(startIdx, endIdx + 1);
    }

    const parsed = JSON.parse(jsonStr);
    return {
      ai_category: String(parsed.category ?? "other").slice(0, 64),
      ai_summary: String(parsed.summary ?? "").slice(0, 500),
      ai_suggested_response: String(parsed.suggested_response ?? "").slice(
        0,
        1000,
      ),
    };
  } catch (err) {
    console.error("Triage LLM failed:", err);
    return {
      ai_category: "other",
      ai_summary: "AI triage failed — manual review required.",
      ai_suggested_response: "",
    };
  }
}

// ── Priority Assignment ────────────────────────────────────────────────

function assignPriority(
  sentiment: string,
  sentimentScore: number,
  category: string,
): number {
  // Priority constants: LOW=10, MEDIUM=20, HIGH=30, URGENT=40

  // Urgent: very negative sentiment + billing/access issues
  if (
    sentiment === "negative" &&
    sentimentScore > 0.85 &&
    ["billing", "access"].includes(category)
  ) {
    return 40;
  }

  // High: negative sentiment or quality/cancellation
  if (sentiment === "negative" && sentimentScore > 0.7) return 30;
  if (["quality", "cancellation"].includes(category)) return 30;

  // Medium: moderate negative or scheduling
  if (sentiment === "negative") return 20;
  if (category === "scheduling") return 20;

  // Low: positive/neutral + feedback/other
  return 10;
}

// ── Privacy Detection via LLaVA ───────────────────────────────────────

async function detectPrivacySensitiveContent(
  ai: Ai,
  imageBytes: Uint8Array,
): Promise<PrivacyDetection> {
  const defaultResult: PrivacyDetection = {
    has_faces: false,
    has_family_photos: false,
    has_sensitive_documents: false,
    detected_items: [],
    privacy_risk_score: 0,
    blur_regions: [],
  };

  try {
    const visionResponse: any = await ai.run(
      "@cf/llava-hf/llava-1.5-7b-hf" as any,
      {
        image: [...imageBytes],
        prompt:
          "You are a privacy-protection AI inspector. Analyze this image for privacy-sensitive content that must be protected. " +
          "Look for: 1) Human faces (any person visible), 2) Family photos or framed pictures on walls/shelves, " +
          "3) Sensitive documents (mail, bills, prescriptions, ID cards, financial papers, screens showing personal data). " +
          "Output ONLY valid JSON with these fields: " +
          '"has_faces" (boolean), "has_family_photos" (boolean), "has_sensitive_documents" (boolean), ' +
          '"detected_items" (array of strings describing each detected item, e.g. "face of adult near kitchen counter"), ' +
          '"privacy_risk_score" (number 0.0-1.0 where 1.0 = many sensitive items found), ' +
          '"blur_regions" (array of objects with "type" being "face"|"photo"|"document", "description" string, "confidence" number 0.0-1.0). ' +
          "If no privacy-sensitive content is found, set all booleans to false and arrays to empty. JSON:",
        max_tokens: 512,
        temperature: 0.1,
      },
    );

    const visionText =
      typeof visionResponse === "string"
        ? visionResponse
        : visionResponse?.response ??
          visionResponse?.description ??
          visionResponse?.result ??
          "";

    // Parse the response
    let jsonStr = visionText.trim();
    const fenceMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (fenceMatch) jsonStr = fenceMatch[1].trim();

    const startIdx = jsonStr.indexOf("{");
    const endIdx = jsonStr.lastIndexOf("}");
    if (startIdx !== -1 && endIdx !== -1) {
      jsonStr = jsonStr.slice(startIdx, endIdx + 1);
    }

    const parsed = JSON.parse(jsonStr);

    return {
      has_faces: Boolean(parsed.has_faces),
      has_family_photos: Boolean(parsed.has_family_photos),
      has_sensitive_documents: Boolean(parsed.has_sensitive_documents),
      detected_items: Array.isArray(parsed.detected_items)
        ? parsed.detected_items.map(String).slice(0, 20)
        : [],
      privacy_risk_score: Math.min(
        1,
        Math.max(0, Number(parsed.privacy_risk_score) || 0),
      ),
      blur_regions: Array.isArray(parsed.blur_regions)
        ? parsed.blur_regions
            .map((r: any) => ({
              type: ["face", "photo", "document"].includes(r.type)
                ? r.type
                : "face",
              description: String(r.description ?? "").slice(0, 200),
              confidence: Math.min(1, Math.max(0, Number(r.confidence) || 0)),
            }))
            .slice(0, 20)
        : [],
    };
  } catch (err) {
    console.error("Privacy detection failed:", err);
    return defaultResult;
  }
}

// ── Store to R2 with privacy metadata ─────────────────────────────────

async function storeToR2WithMetadata(
  bucket: R2Bucket,
  key: string,
  imageBytes: Uint8Array,
  privacyDetection: PrivacyDetection,
  verificationId: number,
  bookingId: number,
): Promise<string> {
  const metadata: Record<string, string> = {
    verification_id: String(verificationId),
    booking_id: String(bookingId),
    privacy_scanned: "true",
    privacy_risk_score: String(privacyDetection.privacy_risk_score),
    has_faces: String(privacyDetection.has_faces),
    has_family_photos: String(privacyDetection.has_family_photos),
    has_sensitive_documents: String(privacyDetection.has_sensitive_documents),
    blur_regions_count: String(privacyDetection.blur_regions.length),
    blur_regions_json: JSON.stringify(privacyDetection.blur_regions).slice(
      0,
      1024,
    ),
    scanned_at: new Date().toISOString(),
  };

  await bucket.put(key, imageBytes, {
    httpMetadata: { contentType: "image/jpeg" },
    customMetadata: metadata,
  });

  return key;
}

// ── Triage Handler ─────────────────────────────────────────────────────

async function handleTriage(
  request: Request,
  env: Env,
): Promise<Response> {
  let body: TriageRequest;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!body.ticket_id || !body.text) {
    return new Response(
      JSON.stringify({ error: "Missing required fields: ticket_id, text" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  // 1. Sentiment analysis
  const combinedText = [body.subject, body.text].filter(Boolean).join(". ");
  const { sentiment, score: sentimentScore } = await analyzeSentiment(
    env.AI,
    combinedText,
  );

  // 2. LLM triage (category, summary, response)
  const llmResult = await runTriageLLM(
    env.AI,
    body.subject || "",
    body.text,
    sentiment,
    body.user_role || "Unknown",
  );

  // 3. Auto-assign priority
  const priority = assignPriority(sentiment, sentimentScore, llmResult.ai_category);

  // 4. Build result
  const result: TriageResult = {
    ticket_id: body.ticket_id,
    sentiment,
    sentiment_score: sentimentScore,
    priority,
    ...llmResult,
  };

  // 5. Callback to Django
  if (body.callback_url) {
    try {
      await fetch(body.callback_url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${env.CLEANABLE_API_KEY}`,
        },
        body: JSON.stringify(result),
      });
    } catch (err) {
      console.error("Callback failed:", err);
    }
  }

  return new Response(JSON.stringify(result), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// ── Vision Verification Handler ────────────────────────────────────────

async function handleVerify(
  request: Request,
  env: Env,
): Promise<Response> {
  let body: VerifyRequest;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!body.verification_id || !body.image_base64) {
    return new Response(
      JSON.stringify({
        error: "Missing required fields: verification_id, image_base64",
      }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  // Decode base64 image
  const imageBytes = Uint8Array.from(atob(body.image_base64), (c) =>
    c.charCodeAt(0),
  );

  // Run vision model (LLaVA)
  let visionText = "";
  try {
    const visionResponse: any = await env.AI.run(
      "@cf/llava-hf/llava-1.5-7b-hf" as any,
      {
        image: [...imageBytes],
        prompt:
          "You are a professional cleaning quality inspector. Analyze this image of a room after cleaning. " +
          "Rate the cleanliness from 0.0 (very dirty) to 1.0 (spotless). " +
          "Identify any issues: stains, clutter, dust, streaks, missed areas, or leftover items. " +
          "Output ONLY valid JSON with these fields: " +
          '"cleanliness_score" (number 0.0-1.0), ' +
          '"summary" (1-2 sentence assessment), ' +
          '"issues" (array of issue strings, empty if none). ' +
          "JSON:",
        max_tokens: 512,
        temperature: 0.1,
      },
    );

    visionText =
      typeof visionResponse === "string"
        ? visionResponse
        : visionResponse?.response ??
          visionResponse?.description ??
          visionResponse?.result ??
          "";
  } catch (err) {
    console.error("Vision model failed:", err);
    visionText = '{"cleanliness_score": 0.5, "summary": "Vision analysis unavailable — manual review required.", "issues": ["analysis_error"]}';
  }

  // Parse vision output
  let cleanlinessScore = 0.5;
  let summary = "Analysis completed.";
  let issues: string[] = [];
  let rawAnalysis: Record<string, unknown> = {};

  try {
    let jsonStr = visionText.trim();
    const fenceMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (fenceMatch) jsonStr = fenceMatch[1].trim();

    const startIdx = jsonStr.indexOf("{");
    const endIdx = jsonStr.lastIndexOf("}");
    if (startIdx !== -1 && endIdx !== -1) {
      jsonStr = jsonStr.slice(startIdx, endIdx + 1);
    }

    const parsed = JSON.parse(jsonStr);
    cleanlinessScore = Math.min(
      1,
      Math.max(0, Number(parsed.cleanliness_score) || 0.5),
    );
    summary = String(parsed.summary ?? "Analysis completed.").slice(0, 500);
    issues = Array.isArray(parsed.issues)
      ? parsed.issues.map(String).slice(0, 10)
      : [];
    rawAnalysis = parsed;
  } catch {
    console.error("Failed to parse vision response:", visionText.slice(0, 200));
    rawAnalysis = { raw_response: visionText.slice(0, 500) };
  }

  // Build result
  const result: VerifyResult = {
    verification_id: body.verification_id,
    cleanliness_score: Math.round(cleanlinessScore * 100) / 100,
    ai_analysis: rawAnalysis,
    ai_summary: summary,
    issues_detected: issues,
  };

  // Callback to Django
  if (body.callback_url) {
    try {
      await fetch(body.callback_url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${env.CLEANABLE_API_KEY}`,
        },
        body: JSON.stringify(result),
      });
    } catch (err) {
      console.error("Verify callback failed:", err);
    }
  }

  return new Response(JSON.stringify(result), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// ── Privacy-Aware Verification Handler ────────────────────────────────

async function handlePrivacyVerify(
  request: Request,
  env: Env,
): Promise<Response> {
  let body: PrivacyVerifyRequest;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!body.verification_id || !body.image_base64) {
    return new Response(
      JSON.stringify({
        error:
          "Missing required fields: verification_id, image_base64",
      }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  // Decode base64 image
  const imageBytes = Uint8Array.from(atob(body.image_base64), (c) =>
    c.charCodeAt(0),
  );

  // ── Step 1: Privacy detection pass ──────────────────────────────────
  const privacyDetection = await detectPrivacySensitiveContent(
    env.AI,
    imageBytes,
  );

  // ── Step 2: Cleanliness verification (same as /verify) ──────────────
  let cleanlinessScore = 0.5;
  let summary = "Analysis completed.";
  let issues: string[] = [];
  let rawAnalysis: Record<string, unknown> = {};

  try {
    const visionResponse: any = await env.AI.run(
      "@cf/llava-hf/llava-1.5-7b-hf" as any,
      {
        image: [...imageBytes],
        prompt:
          "You are a professional cleaning quality inspector. Analyze this image of a room after cleaning. " +
          "Rate the cleanliness from 0.0 (very dirty) to 1.0 (spotless). " +
          "Identify any issues: stains, clutter, dust, streaks, missed areas, or leftover items. " +
          "Output ONLY valid JSON with these fields: " +
          '"cleanliness_score" (number 0.0-1.0), ' +
          '"summary" (1-2 sentence assessment), ' +
          '"issues" (array of issue strings, empty if none). ' +
          "JSON:",
        max_tokens: 512,
        temperature: 0.1,
      },
    );

    const visionText =
      typeof visionResponse === "string"
        ? visionResponse
        : visionResponse?.response ??
          visionResponse?.description ??
          visionResponse?.result ??
          "";

    let jsonStr = visionText.trim();
    const fenceMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (fenceMatch) jsonStr = fenceMatch[1].trim();

    const startIdx = jsonStr.indexOf("{");
    const endIdx = jsonStr.lastIndexOf("}");
    if (startIdx !== -1 && endIdx !== -1) {
      jsonStr = jsonStr.slice(startIdx, endIdx + 1);
    }

    const parsed = JSON.parse(jsonStr);
    cleanlinessScore = Math.min(
      1,
      Math.max(0, Number(parsed.cleanliness_score) || 0.5),
    );
    summary = String(parsed.summary ?? "Analysis completed.").slice(0, 500);
    issues = Array.isArray(parsed.issues)
      ? parsed.issues.map(String).slice(0, 10)
      : [];
    rawAnalysis = parsed;
  } catch (err) {
    console.error("Cleanliness vision failed:", err);
    rawAnalysis = { error: "Vision analysis failed" };
  }

  // ── Step 3: Store to R2 with privacy metadata ───────────────────────
  let r2Key: string | null = null;

  if (body.store_to_r2 && env.VERIFICATION_MEDIA) {
    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      r2Key = `verifications/${body.booking_id}/${body.verification_id}/${timestamp}.jpg`;

      await storeToR2WithMetadata(
        env.VERIFICATION_MEDIA,
        r2Key,
        imageBytes,
        privacyDetection,
        body.verification_id,
        body.booking_id,
      );
    } catch (err) {
      console.error("R2 storage failed:", err);
      r2Key = null;
    }
  }

  // ── Step 4: Build combined result ───────────────────────────────────
  const result: PrivacyVerifyResult = {
    verification_id: body.verification_id,
    privacy_detection: privacyDetection,
    cleanliness_score: Math.round(cleanlinessScore * 100) / 100,
    ai_analysis: {
      ...rawAnalysis,
      privacy: privacyDetection,
    },
    ai_summary: summary,
    issues_detected: issues,
    r2_key: r2Key,
    privacy_scrubbed: privacyDetection.blur_regions.length > 0,
  };

  // ── Step 5: Callback to Django ──────────────────────────────────────
  if (body.callback_url) {
    try {
      await fetch(body.callback_url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${env.CLEANABLE_API_KEY}`,
        },
        body: JSON.stringify(result),
      });
    } catch (err) {
      console.error("Privacy verify callback failed:", err);
    }
  }

  return new Response(JSON.stringify(result), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// ── Main Export ──────────────────────────────────────────────────────

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    // Health check
    if (url.pathname === "/health" && request.method === "GET") {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "cleanable-support-triage",
          models: {
            sentiment: "@cf/huggingface/distilbert-sst-2-int8",
            triage: "@cf/meta/llama-3.2-3b-instruct",
            vision: "@cf/llava-hf/llava-1.5-7b-hf",
          },
          features: {
            privacy_detection: true,
            r2_storage: Boolean(env.VERIFICATION_MEDIA),
          },
          timestamp: new Date().toISOString(),
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    // Auth check for all non-health endpoints
    const authError = validateAuth(request, env);
    if (authError) return authError;

    // Triage endpoint
    if (url.pathname === "/triage" && request.method === "POST") {
      return handleTriage(request, env);
    }

    // Verify endpoint (legacy — cleanliness only)
    if (url.pathname === "/verify" && request.method === "POST") {
      return handleVerify(request, env);
    }

    // Privacy-aware verify endpoint (privacy detection + cleanliness + R2 storage)
    if (url.pathname === "/verify-privacy" && request.method === "POST") {
      return handlePrivacyVerify(request, env);
    }

    return new Response(
      JSON.stringify({
        error: "Not Found",
        endpoints: ["/health", "/triage", "/verify", "/verify-privacy"],
      }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  },
};
