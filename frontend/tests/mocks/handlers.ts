import { http, HttpResponse } from "msw";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Default handler — sukses
export const successHandler = http.post(
    `${API_BASE}/llm/generate/`,
    () => {
        return HttpResponse.json(
            {
                output_json: {
                    summary: "Data extracted successfully",
                    rows: [{ id: 1, value: "test" }],
                },
            },
            { status: 200 }
        );
    }
);

// 401 — API Key invalid
export const handler401 = http.post(
    `${API_BASE}/llm/generate/`,
    () => HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })
);

// 429 — Quota habis
export const handler429 = http.post(
    `${API_BASE}/llm/generate/`,
    () => HttpResponse.json({ detail: "Too Many Requests" }, { status: 429 })
);

// 504 — Gateway Timeout
export const handler504 = http.post(
    `${API_BASE}/llm/generate/`,
    () => HttpResponse.json({ detail: "Gateway Timeout" }, { status: 504 })
);

// Respons dengan skema yang salah (tidak ada output_json)
export const handlerInvalidSchema = http.post(
    `${API_BASE}/llm/generate/`,
    () =>
        HttpResponse.json(
            { wrong_field: "unexpected" },
            { status: 200 }
        )
);

export const handlers = [successHandler];
