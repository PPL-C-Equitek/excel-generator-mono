import { describe, expect, it } from "vitest";
import { ERROR_MESSAGES } from "@/constants/errorMessages";

describe("ERROR_MESSAGES", () => {
  it("contains mapped user-friendly messages for expected status codes", () => {
    expect(ERROR_MESSAGES[401]).toBe("API Key tidak valid");
    expect(ERROR_MESSAGES[429]).toBe("Quota LLM habis, coba lagi nanti");
    expect(ERROR_MESSAGES[503]).toBe("Server sedang tidak tersedia, coba lagi nanti");
    expect(ERROR_MESSAGES[504]).toBe("Request timeout, coba lagi");
  });
});
