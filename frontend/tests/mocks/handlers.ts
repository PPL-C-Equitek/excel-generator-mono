import { http, HttpResponse } from "msw";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export const handler401 = http.post(
    `${API_BASE}/llm/generate/`,
    () => HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })
);

export const handler429 = http.post(
    `${API_BASE}/llm/generate/`,
    () => HttpResponse.json({ detail: "Too Many Requests" }, { status: 429 })
);

export const handler504 = http.post(
    `${API_BASE}/llm/generate/`,
    () => HttpResponse.json({ detail: "Gateway Timeout" }, { status: 504 })
);

export const handlerInvalidSchema = http.post(
    `${API_BASE}/llm/generate/`,
    () =>
        HttpResponse.json(
            { wrong_field: "unexpected" },
            { status: 200 }
        )
);

export const handlerArrayOutput = http.post(
    `${API_BASE}/api/llm/generate/`,
    () =>
        HttpResponse.json(
            { output_json: [{ id: 1, value: "row-a" }, { id: 2, value: "row-b" }] },
            { status: 200 }
        )
);

export const handlerPrimitiveOutput = http.post(
    `${API_BASE}/api/llm/generate/`,
    () =>
        HttpResponse.json(
            { output_json: "hanya sebuah string" },
            { status: 200 }
        )
);

export const handlers = [successHandler];
