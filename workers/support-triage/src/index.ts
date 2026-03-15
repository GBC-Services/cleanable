/**
 * Cloudflare Worker — Support Triage & Spatial Verification
 * ==========================================================
 *
 * Two AI pipelines in one Worker:
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
 * Authentication: Bearer token (CLEANABLE_API_KEY secret)
 */

// ── Types ──────────────────────────────────────────────────────────────

interface Env {
  AI: Ai;
  CLEANABLE_API_KEY: string;
  ENVIRONMENT: string;
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

    // Verify endpoint
    if (url.pathname === "/verify" && request.method === "POST") {
      return handleVerify(request, env);
    }

    return new Response(
      JSON.stringify({
        error: "Not Found",
        endpoints: ["/health", "/triage", "/verify"],
      }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  },
};
