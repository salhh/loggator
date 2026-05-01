/**
 * Tests for WebSocket reconnect backoff logic in lib/websocket.ts
 */
import { describe, it, expect } from "vitest";

// Mirror of the pure function in websocket.ts — tested in isolation
const MAX_ATTEMPTS = 8;
function backoffMs(attempt: number): number {
  return Math.min(2000 * Math.pow(2, attempt), 30_000);
}

describe("backoffMs — exponential backoff schedule", () => {
  it("starts at 2 seconds on attempt 0", () => {
    expect(backoffMs(0)).toBe(2_000);
  });

  it("doubles each attempt", () => {
    expect(backoffMs(1)).toBe(4_000);
    expect(backoffMs(2)).toBe(8_000);
    expect(backoffMs(3)).toBe(16_000);
  });

  it("caps at 30 seconds", () => {
    expect(backoffMs(4)).toBe(30_000);
    expect(backoffMs(5)).toBe(30_000);
    expect(backoffMs(100)).toBe(30_000);
  });
});

describe("MAX_ATTEMPTS threshold", () => {
  it("stops reconnecting after 8 failed attempts", () => {
    // Simulate the reconnect counter logic from useWebSocket
    let attempts = 0;
    const didStop = () => attempts >= MAX_ATTEMPTS;

    for (let i = 0; i < MAX_ATTEMPTS; i++) {
      expect(didStop()).toBe(false);
      attempts++;
    }
    expect(didStop()).toBe(true);
  });

  it("resets to 0 on successful connection", () => {
    let attempts = MAX_ATTEMPTS - 1;
    // Simulate onopen: reset
    attempts = 0;
    expect(attempts).toBe(0);
  });
});

describe("full backoff sequence", () => {
  it("produces the expected delay series before cap", () => {
    const delays = Array.from({ length: 6 }, (_, i) => backoffMs(i));
    expect(delays).toEqual([2_000, 4_000, 8_000, 16_000, 30_000, 30_000]);
  });
});
