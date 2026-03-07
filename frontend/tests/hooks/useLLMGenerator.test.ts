import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLLMGenerator } from "@/hooks/useLLMGenerator";
import type { ILLMService } from "@/lib/ILLMService";

const VALID_JSON_INPUT = '{"key":"value"}';
const VALID_ARRAY_INPUT = '[{"id":1}]';

function makeService(overrides?: Partial<ILLMService>): ILLMService {
    return {
        generate: vi.fn(),
        ...overrides,
    };
}

describe("useLLMGenerator — initial state", () => {
    it("starts with empty input, no result, no error, not loading", () => {
        const { result } = renderHook(() => useLLMGenerator(makeService()));

        expect(result.current.input).toBe("");
        expect(result.current.result).toBeNull();
        expect(result.current.error).toBeNull();
        expect(result.current.loading).toBe(false);
    });
});

describe("useLLMGenerator — input validation (no service call)", () => {
    let service: ILLMService;

    beforeEach(() => {
        service = makeService();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    it("sets error and does not call service when input is empty", async () => {
        const { result } = renderHook(() => useLLMGenerator(service));

        await act(async () => {
            await result.current.handleSubmit();
        });

        expect(result.current.error).toBe("Input tidak boleh kosong");
        expect(service.generate).not.toHaveBeenCalled();
    });

    it("sets error and does not call service when input is whitespace only", async () => {
        const { result } = renderHook(() => useLLMGenerator(service));

        act(() => { result.current.setInput("   "); });
        await act(async () => { await result.current.handleSubmit(); });

        expect(result.current.error).toBe("Input tidak boleh kosong");
        expect(service.generate).not.toHaveBeenCalled();
    });

    it("sets error and does not call service when input is invalid JSON", async () => {
        const { result } = renderHook(() => useLLMGenerator(service));

        act(() => { result.current.setInput("not { json }"); });
        await act(async () => { await result.current.handleSubmit(); });

        expect(result.current.error).toBe("Input harus berupa JSON yang valid");
        expect(service.generate).not.toHaveBeenCalled();
    });

    it("sets error and does not call service when JSON is a primitive (number)", async () => {
        const { result } = renderHook(() => useLLMGenerator(service));

        act(() => { result.current.setInput("42"); });
        await act(async () => { await result.current.handleSubmit(); });

        expect(result.current.error).toBe("Input harus berupa JSON object atau array");
        expect(service.generate).not.toHaveBeenCalled();
    });
});

describe("useLLMGenerator — service call & state transitions", () => {
    let service: ILLMService;

    afterEach(() => {
        vi.clearAllMocks();
    });

    it("calls service and sets result on success (object input)", async () => {
        const mockOutput = { output_json: { summary: "ok" } };
        service = makeService({ generate: vi.fn().mockResolvedValue(mockOutput) });

        const { result } = renderHook(() => useLLMGenerator(service));
        act(() => { result.current.setInput(VALID_JSON_INPUT); });
        await act(async () => { await result.current.handleSubmit(); });

        expect(service.generate).toHaveBeenCalledWith({ key: "value" });
        expect(result.current.result).toEqual(mockOutput);
        expect(result.current.error).toBeNull();
        expect(result.current.loading).toBe(false);
    });

    it("calls service and sets result on success (array input)", async () => {
        const mockOutput = { output_json: [{ id: 1 }] };
        service = makeService({ generate: vi.fn().mockResolvedValue(mockOutput) });

        const { result } = renderHook(() => useLLMGenerator(service));
        act(() => { result.current.setInput(VALID_ARRAY_INPUT); });
        await act(async () => { await result.current.handleSubmit(); });

        expect(service.generate).toHaveBeenCalledWith([{ id: 1 }]);
        expect(result.current.result).toEqual(mockOutput);
        expect(result.current.loading).toBe(false);
    });

    it("sets error message when service throws an Error", async () => {
        service = makeService({
            generate: vi.fn().mockRejectedValue(new Error("API Key tidak valid")),
        });

        const { result } = renderHook(() => useLLMGenerator(service));
        act(() => { result.current.setInput(VALID_JSON_INPUT); });
        await act(async () => { await result.current.handleSubmit(); });

        expect(result.current.error).toBe("API Key tidak valid");
        expect(result.current.result).toBeNull();
        expect(result.current.loading).toBe(false);
    });

    it("sets fallback message when service throws a non-Error value", async () => {
        service = makeService({ generate: vi.fn().mockRejectedValue("fatal") });

        const { result } = renderHook(() => useLLMGenerator(service));
        act(() => { result.current.setInput(VALID_JSON_INPUT); });
        await act(async () => { await result.current.handleSubmit(); });

        expect(result.current.error).toBe("Terjadi kesalahan tidak diketahui");
        expect(result.current.loading).toBe(false);
    });

    it("sets loading=true while service is pending and loading=false after", async () => {
        let resolvePromise!: (v: { output_json: { done: boolean } }) => void;
        const pending = new Promise<{ output_json: { done: boolean } }>(
            (res) => { resolvePromise = res; }
        );
        service = makeService({ generate: vi.fn().mockReturnValue(pending) });

        const { result } = renderHook(() => useLLMGenerator(service));
        act(() => { result.current.setInput(VALID_JSON_INPUT); });

        act(() => { void result.current.handleSubmit(); });
        expect(result.current.loading).toBe(true);

        await act(async () => { resolvePromise({ output_json: { done: true } }); });
        expect(result.current.loading).toBe(false);
    });
});

describe("useLLMGenerator — stale response guard", () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    it("ignores response from a superseded request", async () => {
        const staleOutput = { output_json: { from: "request-1" } };
        const freshOutput = { output_json: { from: "request-2" } };

        let resolveStale!: (v: typeof staleOutput) => void;
        const stalePromise = new Promise<typeof staleOutput>(
            (res) => { resolveStale = res; }
        );

        const service = makeService({
            generate: vi.fn()
                .mockReturnValueOnce(stalePromise)
                .mockResolvedValueOnce(freshOutput),
        });

        const { result } = renderHook(() => useLLMGenerator(service));
        act(() => { result.current.setInput(VALID_JSON_INPUT); });

        act(() => { void result.current.handleSubmit(); });
        await act(async () => { await result.current.handleSubmit(); });
        await act(async () => { resolveStale(staleOutput); });

        expect(result.current.result).toEqual(freshOutput);
    });

    it("ignores error from a superseded request", async () => {
        const freshOutput = { output_json: { from: "request-2" } };

        let rejectStale!: (reason: Error) => void;
        const stalePromise = new Promise<never>(
            (_, rej) => { rejectStale = rej; }
        );

        const service = makeService({
            generate: vi.fn()
                .mockReturnValueOnce(stalePromise)
                .mockResolvedValueOnce(freshOutput),
        });

        const { result } = renderHook(() => useLLMGenerator(service));
        act(() => { result.current.setInput(VALID_JSON_INPUT); });
        act(() => { void result.current.handleSubmit(); });
        await act(async () => { await result.current.handleSubmit(); });
        await act(async () => { rejectStale(new Error("stale error")); });

        expect(result.current.error).toBeNull();
        expect(result.current.result).toEqual(freshOutput);
    });
});
