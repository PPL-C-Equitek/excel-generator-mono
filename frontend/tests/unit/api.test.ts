import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAPI, uploadFile } from "@/lib/api";

describe("fetchAPI", () => {
  const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    if (originalApiUrl) {
      process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
    } else {
      delete process.env.NEXT_PUBLIC_API_URL;
    }
  });

  it("calls API endpoint and returns parsed JSON", async () => {
    const mockedFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", mockedFetch);

    const result = await fetchAPI("health/");

    expect(mockedFetch).toHaveBeenCalledWith("http://localhost:8000/api/health/", {
      headers: {
        "Content-Type": "application/json",
      },
    });
    expect(result).toEqual({ status: "ok" });
  });

  it("throws error when response is not OK", async () => {
    const mockedFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", mockedFetch);

    await expect(fetchAPI("health/")).rejects.toThrow("API error: 500");
  });

  it("normalizes endpoint slashes", async () => {
    const mockedFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", mockedFetch);

    await fetchAPI("/health/");

    expect(mockedFetch).toHaveBeenCalledWith("http://localhost:8000/api/health/", {
      headers: {
        "Content-Type": "application/json",
      },
    });
  });

  it("falls back to default API URL when env URL is invalid", async () => {
    process.env.NEXT_PUBLIC_API_URL = "not-a-valid-url";
    const mockedFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", mockedFetch);

    await fetchAPI("health");

    expect(mockedFetch).toHaveBeenCalledWith("http://localhost:8000/api/health/", {
      headers: {
        "Content-Type": "application/json",
      },
    });
  });
});

describe('uploadFile', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('sends file with correct FormData key', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', filename: 'test.pdf' }),
    })

    const file = new File(['dummy'], 'test.pdf', { type: 'application/pdf' })
    await uploadFile(file)

    const formData = (global.fetch as any).mock.calls[0][1].body as FormData
    expect(formData.get('file')).toBe(file)
  })

  it('throws error when server returns error message', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ status: 'error', message: 'No file provided' }),
    })

    const file = new File(['dummy'], 'test.pdf')
    await expect(uploadFile(file)).rejects.toThrow('No file provided')
  })
})