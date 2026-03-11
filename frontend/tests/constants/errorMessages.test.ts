import { describe, expect, it } from "vitest";
import { ERROR_MESSAGES } from "@/constants/errorMessages";

describe("ERROR_MESSAGES", () => {
  it("contains mapped user-friendly messages for expected status codes", () => {
    expect(ERROR_MESSAGES[401]).toBe("Invalid API key.");
    expect(ERROR_MESSAGES[429]).toBe("Rate limit exceeded. Please try again later.");
    expect(ERROR_MESSAGES[503]).toBe("Service is currently unavailable. Please try again later.");
    expect(ERROR_MESSAGES[504]).toBe("Request timed out. Please try again.");
  });
});
