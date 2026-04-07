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

  if (
    normalized.includes("excel exceeds the maximum allowed sheet count") ||
    normalized.includes("maximum allowed sheet count of 100") ||
    (normalized.includes("excel") && normalized.includes("too many sheets"))
  ) {
    return "Excel has too many sheets (maximum 100).";
  }

  if (normalized.includes("excel") && normalized.includes("password-protected")) {
    return "Excel is password-protected. Please remove the password and try again.";
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
    return "Excel file is corrupt or has an invalid structure.";
  }

  if (
    normalized.includes("rate limit") ||
    normalized.includes("too many request") ||
    normalized.includes("too many upload")
  ) {
    return "Rate limit exceeded. Please try again later.";
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
    let message = "Request failed. Please try again."

    try {
      const data = await res.json()
      if (typeof data?.message === "string") {
        message = data.message
      } else if (typeof data?.detail === "string") {
        message = data.detail
      }
    } catch {
      // ignore JSON parse error
    }

    const error = new Error(message) as HTTPError
    error.status = res.status
    throw error
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
      typeof data?.message === "string"
        ? data.message
        : typeof data?.detail === "string"
          ? data.detail
          : "Upload failed";
    throw new Error(mapUploadErrorMessage(rawMessage));
  }

  return res.json();
}
type HTTPError = Error & {
  status?: number;
};

type AuthResponse = {
  access_token: string
  refresh_token: string
  user: {
    id: number
    email: string
    name: string
  }
}

type MessageResponse = {
  message?: string
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return fetchAPI("auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  }) as Promise<AuthResponse>
}

export async function loginWithGoogle(token: string): Promise<AuthResponse> {
  return fetchAPI("auth/google-oauth/", {
    method: "POST",
    body: JSON.stringify({ token }),
  }) as Promise<AuthResponse>
}

export async function requestPasswordReset(email: string): Promise<MessageResponse> {
  return fetchAPI("auth/forgot-password/", {
    method: "POST",
    body: JSON.stringify({ email }),
  }) as Promise<MessageResponse>
}

export async function resendPasswordReset(email: string): Promise<MessageResponse> {
  return fetchAPI("auth/resend-password-reset/", {
    method: "POST",
    body: JSON.stringify({ email }),
  }) as Promise<MessageResponse>
}
