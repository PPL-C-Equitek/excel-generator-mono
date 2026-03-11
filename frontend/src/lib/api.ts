const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .split("")
  .reduceRight((acc, ch) => (acc === "" && ch === "/" ? acc : ch + acc), "");

function mapUploadErrorMessage(message: string): string {
  const normalized = message.toLowerCase();

  if (
    normalized.includes("file too large") ||
    normalized.includes("maximum allowed size is 10mb")
  ) {
    return "File size too big.";
  }

  if (
    normalized.includes("pdf exceeds the maximum allowed page count") ||
    normalized.includes("maximum allowed page count of 100")
  ) {
    return "PDF has too many pages (maximum 100).";
  }

  if (normalized.includes("password-protected")) {
    return "PDF is password-protected. Please remove the password and try again.";
  }

  if (
    normalized.includes("pdf file is corrupt") ||
    normalized.includes("invalid structure")
  ) {
    return "PDF file is corrupted or invalid.";
  }

  if (
    normalized.includes("invalid or corrupted excel file") ||
    (normalized.includes("excel") && normalized.includes("corrupt")) ||
    (normalized.includes("excel") && normalized.includes("cannot read"))
  ) {
    return "Excel file is corrupted or invalid.";
  }

  return message;
}

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

  const res = await fetch(`${base}/upload/`, {
    method: "POST",
    body,
    ...options,
  });

  if (!res.ok) {
    const data = await res.json();
    const rawMessage =
      typeof data?.message === "string" ? data.message : "Upload failed";
    throw new Error(mapUploadErrorMessage(rawMessage));
  }

  return res.json();
}
