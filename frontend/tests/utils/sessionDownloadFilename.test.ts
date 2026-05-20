import { describe, expect, it } from "vitest";
import { buildSessionOutputDownloadFilename } from "../../src/utils/sessionDownloadFilename";
import type { SessionResumeHistoryOutput } from "../../src/services/sessions";

const baseOutput: SessionResumeHistoryOutput = {
  type: "output",
  id: "abc123",
  output_json: {},
  thinking_log: "",
  reasoning: {},
  created_at: "2026-05-18T10:00:00Z",
};

describe("buildSessionOutputDownloadFilename", () => {
  it("uses export_output_json document_info filename and strips its extension", () => {
    const output: SessionResumeHistoryOutput = {
      ...baseOutput,
      export_output_json: {
        document_info: {
          filename: "C:\\reports\\report.final.xlsx",
        },
      },
    };

    const result = buildSessionOutputDownloadFilename(output, "csv");

    expect(result).toBe("report.final.csv");
  });

  it("falls back to output_json document_info filename when export_output_json is invalid", () => {
    const output: SessionResumeHistoryOutput = {
      ...baseOutput,
      export_output_json: {
        document_info: "invalid",
      },
      output_json: {
        document_info: {
          filename: " report.csv ",
        },
      },
    };

    const result = buildSessionOutputDownloadFilename(output, "xlsx");

    expect(result).toBe("report.xlsx");
  });

  it("ignores blank document_info filenames", () => {
    const output: SessionResumeHistoryOutput = {
      ...baseOutput,
      export_output_json: {
        document_info: {
          filename: "   ",
        },
      },
      output_json: {
        document_info: {
          filename: "invoice.pdf",
        },
      },
    };

    const result = buildSessionOutputDownloadFilename(output, "csv");

    expect(result).toBe("invoice.csv");
  });

  it("falls back to top-level filename when document_info is missing", () => {
    const output: SessionResumeHistoryOutput = {
      ...baseOutput,
      output_json: {
        filename: " summary.csv ",
      },
    };

    const result = buildSessionOutputDownloadFilename(output, "csv");

    expect(result).toBe("summary.csv");
  });

  it("uses output id when filename is not a safe basename", () => {
    const output: SessionResumeHistoryOutput = {
      ...baseOutput,
      output_json: {
        filename: "..",
      },
    };

    const result = buildSessionOutputDownloadFilename(output, "csv");

    expect(result).toBe("output-abc123.csv");
  });

  it("uses output id when output_json is not an object", () => {
    const output: SessionResumeHistoryOutput = {
      ...baseOutput,
      output_json: null as unknown as Record<string, unknown>,
    };

    const result = buildSessionOutputDownloadFilename(output, "xlsx");

    expect(result).toBe("output-abc123.xlsx");
  });

  it("ignores blank top-level filenames", () => {
    const output: SessionResumeHistoryOutput = {
      ...baseOutput,
      output_json: {
        filename: "   ",
      },
    };

    const result = buildSessionOutputDownloadFilename(output, "csv");

    expect(result).toBe("output-abc123.csv");
  });

  it("removes control characters from the basename before building the filename", () => {
    const output: SessionResumeHistoryOutput = {
      ...baseOutput,
      output_json: {
        filename: "report\r\n.csv",
      },
    };

    const result = buildSessionOutputDownloadFilename(output, "csv");

    expect(result).toBe("report.csv");
  });
});
