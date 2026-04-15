import { FILE_TOO_LARGE_MESSAGE } from "@/constants/upload";
import { clearAuthTokens } from "@/lib/auth";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .split("")
  .reduceRight((acc, ch) => (acc === "" && ch === "/" ? acc : ch + acc), "");

function handleUnauthorizedResponse(): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.removeItem("access_token");
    window.localStorage.removeItem("refresh_token");
    window.sessionStorage.removeItem("access_token");
    window.sessionStorage.removeItem("refresh_token");
  } catch {
    // Continue with best-effort cleanup below.
  }

  clearAuthTokens();

  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

function mapUploadErrorMessage(message: string): string {
  const normalized = message.toLowerCase();
  const mentionsPdf = normalized.includes("pdf");
  const mentionsExcel = normalized.includes("excel");
  const mentionsWord =
    /\bword\b/.test(normalized) ||
    normalized.includes(".doc") ||
    normalized.includes(".docx");

  if (
    normalized.includes("file too large") ||
    normalized.includes("maximum allowed size is 10mb")
  ) {
    return FILE_TOO_LARGE_MESSAGE;
  }

  if (
    normalized.includes("pdf exceeds the maximum allowed page count") ||
    (mentionsPdf && normalized.includes("maximum allowed page count of 100"))
  ) {
    return "PDF has too many pages (maximum 100).";
  }

  if (
    normalized.includes("word exceeds the maximum allowed page count") ||
    (mentionsWord && normalized.includes("maximum allowed page count of 100"))
  ) {
    return "Word has too many pages (maximum 100).";
  }

  if (
    normalized.includes("excel exceeds the maximum allowed sheet count") ||
    normalized.includes("maximum allowed sheet count of 100") ||
    (mentionsExcel && normalized.includes("too many sheets"))
  ) {
    return "Excel has too many sheets (maximum 100).";
  }

  if (mentionsExcel && normalized.includes("password-protected")) {
    return "Excel is password-protected. Please remove the password and try again.";
  }

  if (mentionsWord && normalized.includes("password-protected")) {
    return "Word file is password-protected. Please remove the password and try again.";
  }

  if (mentionsPdf && normalized.includes("password-protected")) {
    return "PDF is password-protected. Please remove the password and try again.";
  }

  if (
    mentionsWord &&
    (normalized.includes("corrupt") || normalized.includes("invalid structure"))
  ) {
    return "Word file is corrupt or has an invalid structure.";
  }

  if (
    mentionsPdf &&
    (normalized.includes("pdf file is corrupt") || normalized.includes("invalid structure"))
  ) {
    return "PDF file is corrupted or invalid.";
  }

  if (
    normalized.includes("invalid or corrupted excel file") ||
    (mentionsExcel && normalized.includes("corrupt")) ||
    (mentionsExcel && normalized.includes("cannot read"))
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

  if (normalized.includes("password-protected")) {
    return "File is password-protected. Please remove the password and try again.";
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
    if (res.status === 401) {
      handleUnauthorizedResponse();
    }

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
  const base = API_URL;

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

type ChangePasswordPayload = {
  current_password?: string
  new_password: string
  new_password_confirm: string
  refresh_token?: string
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

export async function logout(accessToken: string, refreshToken: string): Promise<void> {
  const res = await fetch(`${API_URL}/auth/logout/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    let message = "Logout gagal. Silakan coba lagi."

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
}

export async function changePassword(
  accessToken: string,
  payload: ChangePasswordPayload
): Promise<MessageResponse> {
  const res = await fetch(`${API_URL}/auth/change-password/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let message = "Failed to change password."

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

  return res.json()
}
