const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .split("")
  .reduceRight((acc, ch) => (acc === "" && ch === "/" ? acc : ch + acc), "");

export async function fetchAPI(endpoint: string, options?: RequestInit) {
  const normalizedEndpoint = endpoint.replace(/^\/+/, "");
  const res = await fetch(`${API_URL}/${normalizedEndpoint}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}
