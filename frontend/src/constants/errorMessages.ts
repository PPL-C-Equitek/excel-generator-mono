/**
 * Pemetaan HTTP status code → pesan error yang ramah pengguna.
 *
 * Digunakan oleh `generateJson` (llm service) untuk mengubah error
 * API menjadi teks yang bisa langsung ditampilkan di komponen UI.
 *
 * @example
 *   ERROR_MESSAGES[401] // "API Key tidak valid"
 */
export const ERROR_MESSAGES: Record<number, string> = {
    401: "Invalid API key.",
    429: "Rate limit exceeded. Please try again later.",
    503: "Service is currently unavailable. Please try again later.",
    504: "Request timed out. Please try again.",
} as const;
