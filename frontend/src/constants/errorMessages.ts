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
    401: "API Key tidak valid",
    429: "Quota LLM habis, coba lagi nanti",
    503: "Server sedang tidak tersedia, coba lagi nanti",
    504: "Request timeout, coba lagi",
} as const;
