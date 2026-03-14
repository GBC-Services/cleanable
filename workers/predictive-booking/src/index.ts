/**
 * Cloudflare Worker — Predictive Booking Recommendations
 * ======================================================
 *
 * Uses Workers AI (@cf/meta/llama-3.2-3b-instruct) to analyze a Resident's
 * booking history combined with real-time weather data to generate
 * proactive cleaning recommendations.
 *
 * Flow:
 *   1. Receive booking history + property location from Django backend
 *   2. Fetch current/forecast weather from OpenWeatherMap
 *   3. Build a structured prompt with booking patterns + weather context
 *   4. Run inference via Workers AI (Llama 3.2 3B Instruct)
 *   5. Return JSON recommendations to the backend
 *
 * Authentication: Bearer token (CLEANABLE_API_KEY secret)
 */

// ── Types ──────────────────────────────────────────────────────────────

interface Env {
  AI: Ai;
  CLEANABLE_API_KEY: string;
  WEATHER_API_KEY: string;
  ENVIRONMENT: string;
}

interface BookingHistoryEntry {
  booking_id: number;
  service_type: string;
  scheduled_date: string;
  status: string;
  regularity: string;
  bedrooms: number;
  bathrooms: number;
  area_size: number;
  place_type: string;
}

interface RecommendationRequest {
  resident_id: number;
  resident_name: string;
  booking_history: BookingHistoryEntry[];
  location: {
    city: string;
    state: string;
    zip_code: string;
    latitude?: number;
    longitude?: number;
  };
  property: {
    place_type: string;
    bedrooms: number;
    bathrooms: number;
    area_size: number;
  };
}

interface WeatherData {
  current: {
    temp: number;
    humidity: number;
    weather: string;
    description: string;
  };
  forecast: Array<{
    date: string;
    temp_high: number;
    temp_low: number;
    weather: string;
    description: string;
    precipitation_chance: number;
  }>;
}

interface Recommendation {
  type: "deep_clean" | "regular" | "seasonal" | "weather_triggered" | "frequency_adjustment";
  title: string;
  description: string;
  suggested_date: string;
  confidence: number;
  reasoning: string;
  services: string[];
}

interface RecommendationResponse {
  recommendations: Recommendation[];
  weather_context: WeatherData;
  analysis_summary: string;
  generated_at: string;
}

// ── Weather API ──────────────────────────────────────────────────────

async function fetchWeatherData(
  location: RecommendationRequest["location"],
  apiKey: string,
): Promise<WeatherData> {
  const query = location.latitude && location.longitude
    ? `lat=${location.latitude}&lon=${location.longitude}`
    : `zip=${location.zip_code},US`;

  // Current weather
  const currentUrl = `https://api.openweathermap.org/data/2.5/weather?${query}&appid=${apiKey}&units=imperial`;
  const currentRes = await fetch(currentUrl);

  let currentWeather = {
    temp: 72,
    humidity: 50,
    weather: "Clear",
    description: "clear sky",
  };

  if (currentRes.ok) {
    const data: any = await currentRes.json();
    currentWeather = {
      temp: Math.round(data.main?.temp ?? 72),
      humidity: data.main?.humidity ?? 50,
      weather: data.weather?.[0]?.main ?? "Clear",
      description: data.weather?.[0]?.description ?? "clear sky",
    };
  }

  // 5-day forecast
  const forecastUrl = `https://api.openweathermap.org/data/2.5/forecast?${query}&appid=${apiKey}&units=imperial`;
  const forecastRes = await fetch(forecastUrl);

  const forecastDays: WeatherData["forecast"] = [];

  if (forecastRes.ok) {
    const fData: any = await forecastRes.json();
    const dailyMap = new Map<string, any[]>();

    for (const item of fData.list ?? []) {
      const date = item.dt_txt?.split(" ")[0];
      if (date) {
        if (!dailyMap.has(date)) dailyMap.set(date, []);
        dailyMap.get(date)!.push(item);
      }
    }

    for (const [date, items] of dailyMap) {
      const temps = items.map((i: any) => i.main?.temp ?? 72);
      const pops = items.map((i: any) => (i.pop ?? 0) * 100);
      forecastDays.push({
        date,
        temp_high: Math.round(Math.max(...temps)),
        temp_low: Math.round(Math.min(...temps)),
        weather: items[Math.floor(items.length / 2)]?.weather?.[0]?.main ?? "Clear",
        description: items[Math.floor(items.length / 2)]?.weather?.[0]?.description ?? "clear",
        precipitation_chance: Math.round(Math.max(...pops)),
      });

      if (forecastDays.length >= 5) break;
    }
  }

  return { current: currentWeather, forecast: forecastDays };
}

// ── Prompt Builder ──────────────────────────────────────────────────

function buildPrompt(
  request: RecommendationRequest,
  weather: WeatherData,
): string {
  const bookingsSummary = request.booking_history
    .slice(-20) // last 20 bookings
    .map(
      (b) =>
        `- ${b.scheduled_date}: ${b.service_type} (${b.regularity}, ${b.status})`,
    )
    .join("\n");

  const forecastSummary = weather.forecast
    .map(
      (f) =>
        `- ${f.date}: ${f.weather} (${f.temp_low}°F–${f.temp_high}°F, ${f.precipitation_chance}% precip)`,
    )
    .join("\n");

  const today = new Date().toISOString().split("T")[0];

  return `You are a smart home cleaning recommendation engine for Cleanable, a professional cleaning platform. Analyze the data below and output ONLY a valid JSON array of recommendations.

## Resident Profile
- Name: ${request.resident_name}
- Property: ${request.property.place_type}, ${request.property.bedrooms} bed / ${request.property.bathrooms} bath, ${request.property.area_size} sq ft
- Location: ${request.location.city}, ${request.location.state} ${request.location.zip_code}

## Booking History (most recent)
${bookingsSummary || "No previous bookings."}

## Current Weather
- Temperature: ${weather.current.temp}°F
- Humidity: ${weather.current.humidity}%
- Conditions: ${weather.current.weather} — ${weather.current.description}

## 5-Day Forecast
${forecastSummary || "Forecast unavailable."}

## Today's Date
${today}

## Instructions
Generate 2–4 cleaning recommendations based on:
1. **Booking frequency patterns** — If they book weekly, suggest the next expected date. If overdue, flag it.
2. **Weather triggers** — Heavy rain/snow → suggest a deep clean 1-2 days after storms. High pollen seasons → suggest allergen cleaning. High humidity → suggest mold prevention cleaning.
3. **Seasonal patterns** — Spring deep cleans, fall gutter/exterior prep, winter holiday prep.
4. **Property-specific** — Larger homes may need more frequent cleaning. Commercial properties have different needs.

Output ONLY a JSON array. Each element must have:
- "type": one of "deep_clean", "regular", "seasonal", "weather_triggered", "frequency_adjustment"
- "title": short title (max 60 chars)
- "description": 1-2 sentence explanation
- "suggested_date": "YYYY-MM-DD" format
- "confidence": 0.0 to 1.0
- "reasoning": brief reasoning
- "services": array of suggested cleaning services (e.g., ["Standard Clean", "Deep Clean", "Window Washing"])

JSON array:`;
}

// ── AI Inference ────────────────────────────────────────────────────

async function runInference(
  ai: Ai,
  prompt: string,
): Promise<Recommendation[]> {
  const response: any = await ai.run("@cf/meta/llama-3.2-3b-instruct", {
    messages: [
      {
        role: "system",
        content:
          "You are a JSON-only response bot. Output valid JSON arrays. No markdown, no explanations, no code fences. Just the JSON array.",
      },
      { role: "user", content: prompt },
    ],
    max_tokens: 1024,
    temperature: 0.3,
    top_p: 0.9,
  });

  const text =
    typeof response === "string"
      ? response
      : response?.response ?? response?.result ?? "";

  // Extract JSON from the response (handle cases where model wraps in ```json)
  let jsonStr = text.trim();

  // Strip code fences if present
  const fenceMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenceMatch) {
    jsonStr = fenceMatch[1].trim();
  }

  // Find the JSON array boundaries
  const startIdx = jsonStr.indexOf("[");
  const endIdx = jsonStr.lastIndexOf("]");
  if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
    jsonStr = jsonStr.slice(startIdx, endIdx + 1);
  }

  try {
    const parsed = JSON.parse(jsonStr);
    if (!Array.isArray(parsed)) return [];

    // Validate and sanitize each recommendation
    return parsed
      .filter(
        (r: any) =>
          r.type && r.title && r.description && r.suggested_date,
      )
      .map((r: any) => ({
        type: r.type,
        title: String(r.title).slice(0, 60),
        description: String(r.description).slice(0, 300),
        suggested_date: String(r.suggested_date),
        confidence: Math.min(1, Math.max(0, Number(r.confidence) || 0.5)),
        reasoning: String(r.reasoning ?? "").slice(0, 200),
        services: Array.isArray(r.services)
          ? r.services.map(String).slice(0, 5)
          : ["Standard Clean"],
      }))
      .slice(0, 4);
  } catch {
    console.error("Failed to parse AI response:", jsonStr.slice(0, 200));
    return [];
  }
}

// ── Request Handler ─────────────────────────────────────────────────

async function handleRecommendation(
  request: Request,
  env: Env,
): Promise<Response> {
  // Validate auth
  const authHeader = request.headers.get("Authorization");
  if (!authHeader || authHeader !== `Bearer ${env.CLEANABLE_API_KEY}`) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Parse body
  let body: RecommendationRequest;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!body.resident_id || !body.location) {
    return new Response(
      JSON.stringify({ error: "Missing required fields: resident_id, location" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  // Fetch weather data
  const weather = await fetchWeatherData(body.location, env.WEATHER_API_KEY);

  // Build prompt and run AI
  const prompt = buildPrompt(body, weather);
  const recommendations = await runInference(env.AI, prompt);

  // Build analysis summary
  const bookingCount = body.booking_history?.length ?? 0;
  const lastBooking = body.booking_history?.[bookingCount - 1];
  const analysisSummary = `Analyzed ${bookingCount} historical booking(s) for ${body.resident_name}. ` +
    `Property: ${body.property.place_type} (${body.property.bedrooms}BR/${body.property.bathrooms}BA, ${body.property.area_size} sqft). ` +
    `Current conditions: ${weather.current.weather} at ${weather.current.temp}°F. ` +
    (lastBooking
      ? `Last booking: ${lastBooking.scheduled_date} (${lastBooking.service_type}).`
      : "No previous bookings on record.");

  const response: RecommendationResponse = {
    recommendations,
    weather_context: weather,
    analysis_summary: analysisSummary,
    generated_at: new Date().toISOString(),
  };

  return new Response(JSON.stringify(response), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "private, max-age=3600",
    },
  });
}

// ── Main Export ──────────────────────────────────────────────────────

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
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
          service: "cleanable-predictive-booking",
          model: "@cf/meta/llama-3.2-3b-instruct",
          timestamp: new Date().toISOString(),
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    // Recommendation endpoint
    if (url.pathname === "/recommend" && request.method === "POST") {
      return handleRecommendation(request, env);
    }

    return new Response(
      JSON.stringify({ error: "Not Found", endpoints: ["/recommend", "/health"] }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  },
};
