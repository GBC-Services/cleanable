/**
 * Cleanable Platform — k6 Load Test Suite
 * ==========================================
 *
 * Simulates real-world traffic patterns across three critical paths:
 *   1. Concurrent Booking Flow (Resident → Service Pro assignment)
 *   2. Heavy WebSocket GPS Tracking (Service Pro location updates)
 *   3. AI Inference Requests (Cloudflare Workers AI endpoints)
 *
 * Usage:
 *   k6 run tests/load/k6-load-test.js
 *   k6 run --vus 100 --duration 5m tests/load/k6-load-test.js
 *   k6 run --env BASE_URL=https://staging.cleanable.app tests/load/k6-load-test.js
 *
 * Environment variables:
 *   BASE_URL          — API base URL (default: http://localhost:8000)
 *   WS_URL            — WebSocket URL (default: ws://localhost:8000)
 *   CF_WORKER_URL     — Cloudflare Worker URL (default: http://localhost:8787)
 *   RESIDENT_EMAIL    — Test resident email
 *   RESIDENT_PASSWORD — Test resident password
 *   PRO_EMAIL         — Test service pro email
 *   PRO_PASSWORD      — Test service pro password
 */

import http from "k6/http";
import ws from "k6/ws";
import { check, group, sleep, fail } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";
import { randomIntBetween } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";

// ── Configuration ───────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const WS_URL = __ENV.WS_URL || "ws://localhost:8000";
const CF_WORKER_URL = __ENV.CF_WORKER_URL || "http://localhost:8787";

const RESIDENT_EMAIL = __ENV.RESIDENT_EMAIL || "loadtest-resident@cleanable.test";
const RESIDENT_PASSWORD = __ENV.RESIDENT_PASSWORD || "LoadTest2026!";
const PRO_EMAIL = __ENV.PRO_EMAIL || "loadtest-pro@cleanable.test";
const PRO_PASSWORD = __ENV.PRO_PASSWORD || "LoadTest2026!";

// ── Custom Metrics ──────────────────────────────────────────────────

const bookingCreated = new Counter("bookings_created");
const bookingFailed = new Counter("bookings_failed");
const bookingDuration = new Trend("booking_creation_duration", true);

const gpsUpdatesSent = new Counter("gps_updates_sent");
const gpsUpdatesFailed = new Counter("gps_updates_failed");
const gpsLatency = new Trend("gps_update_latency", true);

const aiInferenceRequests = new Counter("ai_inference_requests");
const aiInferenceFailed = new Counter("ai_inference_failed");
const aiInferenceDuration = new Trend("ai_inference_duration", true);

const wsConnections = new Counter("ws_connections_total");
const wsConnectionsFailed = new Counter("ws_connections_failed");
const wsMessageLatency = new Trend("ws_message_latency", true);

const errorRate = new Rate("error_rate");

// ── Load Stages ─────────────────────────────────────────────────────

export const options = {
  scenarios: {
    // Scenario 1: Booking flow — ramp up concurrent Residents
    bookings: {
      executor: "ramping-vus",
      exec: "bookingFlow",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 10 },  // Warm up
        { duration: "1m", target: 50 },   // Ramp to 50 concurrent
        { duration: "2m", target: 100 },  // Sustained load
        { duration: "1m", target: 200 },  // Peak load
        { duration: "30s", target: 0 },   // Cool down
      ],
      gracefulRampDown: "10s",
    },

    // Scenario 2: GPS WebSocket — constant stream of location updates
    gps_tracking: {
      executor: "constant-vus",
      exec: "gpsTrackingFlow",
      vus: 50,         // 50 concurrent Service Pros
      duration: "5m",
      startTime: "30s", // Start after bookings warm up
    },

    // Scenario 3: AI inference — burst + sustained pattern
    ai_inference: {
      executor: "ramping-arrival-rate",
      exec: "aiInferenceFlow",
      startRate: 5,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 200,
      stages: [
        { duration: "30s", target: 10 },  // Warm up
        { duration: "2m", target: 30 },   // Sustained
        { duration: "30s", target: 60 },  // Burst
        { duration: "1m", target: 20 },   // Settle
        { duration: "30s", target: 0 },   // Cool down
      ],
      startTime: "1m",
    },
  },

  thresholds: {
    // Global
    http_req_duration: ["p(95)<2000", "p(99)<5000"],
    error_rate: ["rate<0.05"],  // Less than 5% errors

    // Bookings
    booking_creation_duration: ["p(95)<3000"],
    bookings_failed: ["count<10"],

    // GPS
    gps_update_latency: ["p(95)<500"],     // GPS must be fast
    ws_message_latency: ["p(95)<200"],

    // AI Inference
    ai_inference_duration: ["p(95)<10000"], // AI can be slower
  },
};

// ═══════════════════════════════════════════════════════════════════
//  HELPER: JWT Authentication
// ═══════════════════════════════════════════════════════════════════

function authenticate(email, password) {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/token/`,
    JSON.stringify({ email, password }),
    { headers: { "Content-Type": "application/json" }, tags: { name: "auth" } }
  );

  const ok = check(res, {
    "auth: status 200": (r) => r.status === 200,
    "auth: has access token": (r) => {
      try { return JSON.parse(r.body).access !== undefined; }
      catch { return false; }
    },
  });

  if (!ok) {
    errorRate.add(1);
    fail(`Authentication failed for ${email}: ${res.status} ${res.body}`);
  }

  errorRate.add(0);
  const tokens = JSON.parse(res.body);
  return tokens.access;
}

function authHeaders(token) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

// ═══════════════════════════════════════════════════════════════════
//  SCENARIO 1: Concurrent Booking Flow
// ═══════════════════════════════════════════════════════════════════

export function bookingFlow() {
  const token = authenticate(RESIDENT_EMAIL, RESIDENT_PASSWORD);

  group("Booking Flow", () => {
    // Step 1: List available services
    const servicesRes = http.get(`${BASE_URL}/api/v1/bookings/services/`, {
      headers: authHeaders(token),
      tags: { name: "list_services" },
    });

    check(servicesRes, {
      "services: status 200": (r) => r.status === 200,
    });

    sleep(randomIntBetween(1, 3)); // User browses

    // Step 2: Check availability for a date
    const targetDate = new Date();
    targetDate.setDate(targetDate.getDate() + randomIntBetween(1, 14));
    const dateStr = targetDate.toISOString().split("T")[0];

    const availRes = http.get(
      `${BASE_URL}/api/v1/bookings/availability/?date=${dateStr}`,
      {
        headers: authHeaders(token),
        tags: { name: "check_availability" },
      }
    );

    check(availRes, {
      "availability: status 200": (r) => r.status === 200,
    });

    sleep(randomIntBetween(1, 2)); // User picks a slot

    // Step 3: Create booking
    const bookingPayload = {
      service_type: "standard_clean",
      scheduled_date: dateStr,
      scheduled_time: `${randomIntBetween(8, 17)}:00`,
      duration_hours: randomIntBetween(2, 4),
      address: `${randomIntBetween(100, 9999)} Load Test Ave, Suite ${randomIntBetween(1, 20)}`,
      special_instructions: `k6 load test - VU ${__VU} iter ${__ITER}`,
      bedrooms: randomIntBetween(1, 5),
      bathrooms: randomIntBetween(1, 3),
    };

    const start = Date.now();
    const bookingRes = http.post(
      `${BASE_URL}/api/v1/bookings/`,
      JSON.stringify(bookingPayload),
      {
        headers: authHeaders(token),
        tags: { name: "create_booking" },
      }
    );
    const elapsed = Date.now() - start;

    const bookingOk = check(bookingRes, {
      "booking: status 201": (r) => r.status === 201,
      "booking: has id": (r) => {
        try { return JSON.parse(r.body).id !== undefined; }
        catch { return false; }
      },
    });

    if (bookingOk) {
      bookingCreated.add(1);
      bookingDuration.add(elapsed);
      errorRate.add(0);

      // Step 4: Fetch booking detail
      const bookingId = JSON.parse(bookingRes.body).id;
      const detailRes = http.get(
        `${BASE_URL}/api/v1/bookings/${bookingId}/`,
        {
          headers: authHeaders(token),
          tags: { name: "booking_detail" },
        }
      );

      check(detailRes, {
        "detail: status 200": (r) => r.status === 200,
      });
    } else {
      bookingFailed.add(1);
      errorRate.add(1);
    }

    sleep(randomIntBetween(2, 5)); // Think time between bookings
  });
}

// ═══════════════════════════════════════════════════════════════════
//  SCENARIO 2: WebSocket GPS Tracking
// ═══════════════════════════════════════════════════════════════════

export function gpsTrackingFlow() {
  const token = authenticate(PRO_EMAIL, PRO_PASSWORD);

  // Simulate a random active booking ID
  const bookingId = randomIntBetween(1, 1000);

  // Base coordinates (varies per VU to spread across map)
  const baseLat = 29.7604 + ((__VU % 20) * 0.01);  // Houston area
  const baseLng = -95.3698 + ((__VU % 15) * 0.01);

  group("GPS WebSocket Tracking", () => {
    const wsUrl = `${WS_URL}/ws/tracking/${bookingId}/?token=${token}`;

    const res = ws.connect(wsUrl, { tags: { name: "ws_gps" } }, (socket) => {
      wsConnections.add(1);

      let msgCount = 0;
      const maxMessages = 60; // ~3 minutes at 3s intervals

      socket.on("open", () => {
        console.log(`[VU ${__VU}] GPS WebSocket connected for booking ${bookingId}`);

        // Send GPS updates every 3 seconds
        const interval = setInterval(() => {
          if (msgCount >= maxMessages) {
            clearInterval(interval);
            socket.close();
            return;
          }

          // Simulate movement along a route
          const progress = msgCount / maxMessages;
          const lat = baseLat + progress * 0.05;
          const lng = baseLng + progress * 0.03;

          const gpsPayload = {
            type: "gps_update",
            data: {
              latitude: lat + (Math.random() - 0.5) * 0.0001,
              longitude: lng + (Math.random() - 0.5) * 0.0001,
              accuracy: randomIntBetween(3, 25),
              heading: randomIntBetween(0, 359),
              speed: randomIntBetween(0, 35),
              timestamp: new Date().toISOString(),
              booking_id: bookingId,
            },
          };

          const sendStart = Date.now();
          socket.send(JSON.stringify(gpsPayload));
          gpsUpdatesSent.add(1);
          gpsLatency.add(Date.now() - sendStart);
          msgCount++;
        }, 3000);
      });

      socket.on("message", (data) => {
        const receiveTime = Date.now();
        try {
          const msg = JSON.parse(data);
          if (msg.type === "location_ack") {
            wsMessageLatency.add(receiveTime - new Date(msg.server_timestamp).getTime());
          }
        } catch {
          // Non-JSON message
        }
        errorRate.add(0);
      });

      socket.on("error", (e) => {
        console.error(`[VU ${__VU}] WS error:`, e.error());
        wsConnectionsFailed.add(1);
        errorRate.add(1);
      });

      socket.on("close", () => {
        console.log(`[VU ${__VU}] WS closed after ${msgCount} messages`);
      });

      // Keep alive for the duration
      socket.setTimeout(() => {
        socket.close();
      }, 180000); // 3 minutes max
    });

    check(res, {
      "ws: connection established": (r) => r && r.status === 101,
    });
  });

  // Also test HTTP GPS fallback endpoint (for offline → sync scenarios)
  group("GPS HTTP Fallback", () => {
    for (let i = 0; i < 10; i++) {
      const payload = {
        booking_id: bookingId,
        latitude: baseLat + Math.random() * 0.01,
        longitude: baseLng + Math.random() * 0.01,
        accuracy: randomIntBetween(5, 30),
        heading: randomIntBetween(0, 359),
        speed: randomIntBetween(0, 25),
        timestamp: new Date().toISOString(),
      };

      const start = Date.now();
      const res = http.post(
        `${BASE_URL}/api/v1/iot/gps/report/`,
        JSON.stringify(payload),
        {
          headers: authHeaders(token),
          tags: { name: "gps_http_report" },
        }
      );

      const ok = check(res, {
        "gps http: status 2xx": (r) => r.status >= 200 && r.status < 300,
      });

      if (ok) {
        gpsLatency.add(Date.now() - start);
        errorRate.add(0);
      } else {
        gpsUpdatesFailed.add(1);
        errorRate.add(1);
      }

      sleep(0.5);
    }
  });
}

// ═══════════════════════════════════════════════════════════════════
//  SCENARIO 3: AI Inference Requests
// ═══════════════════════════════════════════════════════════════════

export function aiInferenceFlow() {
  group("AI Inference", () => {
    // Randomly pick one of three AI inference types
    const inferenceType = randomIntBetween(1, 3);

    switch (inferenceType) {
      case 1:
        testSupportTriage();
        break;
      case 2:
        testVerificationVision();
        break;
      case 3:
        testPrivacyDetection();
        break;
    }
  });
}

/**
 * Test 1: Support Ticket Triage via CF Worker
 * DistilBERT sentiment + Llama category classification
 */
function testSupportTriage() {
  const ticketBodies = [
    "My cleaner didn't show up and I've been waiting for 2 hours. This is unacceptable!",
    "Great service today, the apartment looks amazing. Thank you!",
    "I need to reschedule my booking for next Tuesday. Can someone help?",
    "There was a billing error on my last invoice. I was charged twice.",
    "The cleaner broke a vase in my living room during the session.",
    "How do I add a new property to my account?",
    "Your app keeps crashing when I try to view my booking history.",
    "I'd like to leave a 5-star review for Maria, she did an outstanding job.",
  ];

  const payload = {
    ticket_id: randomIntBetween(10000, 99999),
    body: ticketBodies[randomIntBetween(0, ticketBodies.length - 1)],
    subject: "Load Test Ticket",
    customer_email: `loadtest-${__VU}@cleanable.test`,
    callback_url: `${BASE_URL}/api/v1/support/webhooks/triage-result/`,
  };

  const start = Date.now();
  const res = http.post(
    `${CF_WORKER_URL}/triage`,
    JSON.stringify(payload),
    {
      headers: { "Content-Type": "application/json" },
      tags: { name: "ai_triage" },
      timeout: "30s",
    }
  );
  const elapsed = Date.now() - start;

  const ok = check(res, {
    "triage: status 2xx": (r) => r.status >= 200 && r.status < 300,
    "triage: has sentiment": (r) => {
      try { return JSON.parse(r.body).sentiment !== undefined; }
      catch { return false; }
    },
    "triage: under 10s": () => elapsed < 10000,
  });

  aiInferenceRequests.add(1);
  aiInferenceDuration.add(elapsed);

  if (!ok) {
    aiInferenceFailed.add(1);
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

/**
 * Test 2: Verification Vision (room cleanliness scoring)
 * LLaVA 1.5 7B vision model via CF Worker
 */
function testVerificationVision() {
  // Simulate sending a small test image (base64 encoded 1x1 pixel PNG)
  const testImageBase64 =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg==";

  const payload = {
    verification_id: randomIntBetween(1, 10000),
    image_data: testImageBase64,
    booking_id: randomIntBetween(1, 1000),
    callback_url: `${BASE_URL}/api/v1/support/webhooks/verification-result/`,
  };

  const start = Date.now();
  const res = http.post(
    `${CF_WORKER_URL}/verify`,
    JSON.stringify(payload),
    {
      headers: { "Content-Type": "application/json" },
      tags: { name: "ai_verify" },
      timeout: "30s",
    }
  );
  const elapsed = Date.now() - start;

  const ok = check(res, {
    "verify: status 2xx": (r) => r.status >= 200 && r.status < 300,
    "verify: under 15s": () => elapsed < 15000,
  });

  aiInferenceRequests.add(1);
  aiInferenceDuration.add(elapsed);

  if (!ok) {
    aiInferenceFailed.add(1);
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

/**
 * Test 3: Privacy Detection (face/document blur detection)
 * LLaVA vision model via CF Worker /verify-privacy endpoint
 */
function testPrivacyDetection() {
  const testImageBase64 =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg==";

  const payload = {
    verification_id: randomIntBetween(1, 10000),
    image_data: testImageBase64,
    booking_id: randomIntBetween(1, 1000),
    callback_url: `${BASE_URL}/api/v1/support/webhooks/verification-result/`,
  };

  const start = Date.now();
  const res = http.post(
    `${CF_WORKER_URL}/verify-privacy`,
    JSON.stringify(payload),
    {
      headers: { "Content-Type": "application/json" },
      tags: { name: "ai_privacy" },
      timeout: "30s",
    }
  );
  const elapsed = Date.now() - start;

  const ok = check(res, {
    "privacy: status 2xx": (r) => r.status >= 200 && r.status < 300,
    "privacy: has blur_regions": (r) => {
      try { return JSON.parse(r.body).privacy_detection !== undefined; }
      catch { return false; }
    },
    "privacy: under 15s": () => elapsed < 15000,
  });

  aiInferenceRequests.add(1);
  aiInferenceDuration.add(elapsed);

  if (!ok) {
    aiInferenceFailed.add(1);
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

// ── Summary Reporter ────────────────────────────────────────────────

export function handleSummary(data) {
  return {
    "tests/load/results/summary.json": JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: "  ", enableColors: true }),
  };
}

function textSummary(data) {
  const m = data.metrics;
  return `
╔══════════════════════════════════════════════════════════════╗
║               CLEANABLE LOAD TEST RESULTS                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  BOOKINGS                                                    ║
║  ├─ Created:    ${pad(m.bookings_created?.values?.count || 0)}  ║
║  ├─ Failed:     ${pad(m.bookings_failed?.values?.count || 0)}   ║
║  └─ p95 Duration: ${pad(Math.round(m.booking_creation_duration?.values?.["p(95)"] || 0))} ms  ║
║                                                              ║
║  GPS TRACKING                                                ║
║  ├─ Updates Sent:   ${pad(m.gps_updates_sent?.values?.count || 0)} ║
║  ├─ Updates Failed: ${pad(m.gps_updates_failed?.values?.count || 0)} ║
║  ├─ p95 Latency:    ${pad(Math.round(m.gps_update_latency?.values?.["p(95)"] || 0))} ms ║
║  └─ WS Connections: ${pad(m.ws_connections_total?.values?.count || 0)} ║
║                                                              ║
║  AI INFERENCE                                                ║
║  ├─ Requests:  ${pad(m.ai_inference_requests?.values?.count || 0)} ║
║  ├─ Failed:    ${pad(m.ai_inference_failed?.values?.count || 0)}   ║
║  └─ p95 Duration: ${pad(Math.round(m.ai_inference_duration?.values?.["p(95)"] || 0))} ms ║
║                                                              ║
║  OVERALL                                                     ║
║  ├─ Error Rate: ${pad(((m.error_rate?.values?.rate || 0) * 100).toFixed(2))}%  ║
║  └─ HTTP p95:   ${pad(Math.round(m.http_req_duration?.values?.["p(95)"] || 0))} ms    ║
╚══════════════════════════════════════════════════════════════╝
  `;
}

function pad(val, width = 8) {
  return String(val).padStart(width);
}
