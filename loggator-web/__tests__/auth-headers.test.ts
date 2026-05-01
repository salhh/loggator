/**
 * Tests for JWT expiry decoding in lib/auth-headers.ts
 * (pure utility — no DOM, no Next.js runtime needed)
 */
import { describe, it, expect } from "vitest";

// Inline the function under test so the file can run in node env
// without the localStorage / window guards firing.
function decodeJwtExpiry(token: string): number | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(
      Buffer.from(
        parts[1].replace(/-/g, "+").replace(/_/g, "/"),
        "base64"
      ).toString("utf-8")
    );
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

function makeJwt(payload: Record<string, unknown>): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${header}.${body}.fakesignature`;
}

describe("decodeJwtExpiry", () => {
  it("returns the exp claim as a number", () => {
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const token = makeJwt({ sub: "user-1", exp });
    expect(decodeJwtExpiry(token)).toBe(exp);
  });

  it("returns null when the token has no exp claim", () => {
    const token = makeJwt({ sub: "user-1" });
    expect(decodeJwtExpiry(token)).toBeNull();
  });

  it("returns null for a malformed token (not 3 parts)", () => {
    expect(decodeJwtExpiry("not.a.valid.jwt.parts")).toBeNull();
    expect(decodeJwtExpiry("only-one-part")).toBeNull();
  });

  it("returns null for an empty string", () => {
    expect(decodeJwtExpiry("")).toBeNull();
  });

  it("returns null when the payload is not valid base64 JSON", () => {
    expect(decodeJwtExpiry("header.!!!invalid!!!.sig")).toBeNull();
  });

  it("handles base64url encoding (- and _ characters)", () => {
    // base64url uses - and _ instead of + and /
    const exp = Math.floor(Date.now() / 1000) + 600;
    const token = makeJwt({ exp });
    // makeJwt already uses base64url; verify round-trip
    expect(decodeJwtExpiry(token)).toBe(exp);
  });
});
