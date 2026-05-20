import type { SessionResumeHistoryOutput } from "@/services/sessions";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getDocumentInfoFilename(payload: unknown): string | null {
  if (!isRecord(payload)) {
    return null;
  }

  const documentInfo = payload.document_info;
  if (!isRecord(documentInfo)) {
    return null;
  }

  return typeof documentInfo.filename === "string" && documentInfo.filename.trim()
    ? documentInfo.filename.trim()
    : null;
}

function getTopLevelFilename(payload: unknown): string | null {
  if (!isRecord(payload)) {
    return null;
  }

  return typeof payload.filename === "string" && payload.filename.trim()
    ? payload.filename.trim()
    : null;
}

function toSafeBasename(filename: string): string | null {
  const basename = filename.replaceAll("\\", "/").split("/").pop()?.trim();
  if (!basename || basename === "." || basename === "..") {
    return null;
  }

  return basename.replace(/[\r\n]/g, "");
}

export function buildSessionOutputDownloadFilename(
  output: SessionResumeHistoryOutput,
  extension: "csv" | "xlsx",
): string {
  const originalName =
    getDocumentInfoFilename(output.export_output_json) ||
    getDocumentInfoFilename(output.output_json) ||
    getTopLevelFilename(output.output_json);
  const basename = originalName ? toSafeBasename(originalName) : null;
  const root = basename?.replace(/\.[^/.]*$/, "") || `output-${output.id}`;

  return `${root}.${extension}`;
}
