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
    `${API_BASE}/llm/generate/`,
    () =>
        HttpResponse.json(
            { output_json: [{ id: 1, value: "row-a" }, { id: 2, value: "row-b" }] },
            { status: 200 }
        )
);

export const handlerPrimitiveOutput = http.post(
    `${API_BASE}/llm/generate/`,
    () =>
        HttpResponse.json(
            { output_json: "hanya sebuah string" },
            { status: 200 }
        )
);

export const exportCsvSuccessHandler = http.post(
    `${API_BASE}/export/csv`,
    () => HttpResponse.json({ file_id: "csv_12345" }, { status: 200 })
);

export const exportCsvInvalidSchemaHandler = http.post(
    `${API_BASE}/export/csv`,
    () => HttpResponse.json({ missing: "file_id" }, { status: 200 })
);

export const exportCsvInvalidPrefixHandler = http.post(
    `${API_BASE}/export/csv`,
    () => HttpResponse.json({ file_id: "wrong_999" }, { status: 200 })
);

export const exportExcelSuccessHandler = http.post(
    `${API_BASE}/export/excel`,
    () =>
        HttpResponse.json(
            {
                file_id: "xlsx_12345",
                file_name: "export_12345.xlsx",
                artifact_type: "xlsx",
                size_bytes: 1024,
                created_at: "2026-04-01T10:00:00Z",
            },
            { status: 200 }
        )
);

export const exportExcelInvalidSchemaHandler = http.post(
    `${API_BASE}/export/excel`,
    () => HttpResponse.json({ missing: "file_id" }, { status: 200 })
);

export const exportExcelInvalidPrefixHandler = http.post(
    `${API_BASE}/export/excel`,
    () =>
        HttpResponse.json(
            {
                file_id: "wrong_12345",
                file_name: "export_12345.xlsx",
                artifact_type: "xlsx",
            },
            { status: 200 }
        )
);

export const exportExcelInvalidArtifactTypeHandler = http.post(
    `${API_BASE}/export/excel`,
    () =>
        HttpResponse.json(
            {
                file_id: "xlsx_12345",
                file_name: "export_12345.xlsx",
                artifact_type: "csv",
            },
            { status: 200 }
        )
);

export const exportExcelInvalidFileNameHandler = http.post(
    `${API_BASE}/export/excel`,
    () =>
        HttpResponse.json(
            {
                file_id: "xlsx_12345",
                file_name: "export_12345.csv",
                artifact_type: "xlsx",
            },
            { status: 200 }
        )
);

export const handlers = [successHandler];
