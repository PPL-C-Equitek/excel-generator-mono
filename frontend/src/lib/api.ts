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

export async function uploadFile(file: File, options?: RequestInit) {
  const base = (() => {
    try {
      return new URL(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").origin;
    } catch {
      return "http://localhost:8000";
    }
  })();

  const body = new FormData();
  body.append("file", file);

  const res = await fetch(`${base}/api/upload/`, {
    method: "POST",
    body,
    ...options,
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.message || "Upload failed");
  }

  return res.json();
}
