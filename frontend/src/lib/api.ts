const DEFAULT_API_URL = 'http://localhost:8000';

function normalizeApiBase(rawUrl?: string) {
  const value = (rawUrl ?? DEFAULT_API_URL).trim();
  try {
    const parsed = new URL(value);
    return parsed.origin;
  } catch {
    return DEFAULT_API_URL;
  }
}

function buildApiUrl(endpoint: string) {
  const base = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL);
  const cleanedEndpoint = endpoint.replace(/^\/+|\/+$/g, '');
  return `${base}/api/${cleanedEndpoint}/`;
}

export async function fetchAPI(endpoint: string, options?: RequestInit) {
  const res = await fetch(buildApiUrl(endpoint), {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

export async function uploadFile(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(buildApiUrl('upload'), {
    method: 'POST',
    body: formData,
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.message || 'Upload failed')
  }

  return data
}