export interface ThinkingPanelProps {
  status: "idle" | "thinking" | "success" | "error";
  content: string;
}

const containerClassName =
  "max-h-[400px] overflow-y-auto rounded-md border border-gray-200 bg-white p-4";

export default function ThinkingPanel({
  status,
  content,
}: Readonly<ThinkingPanelProps>) {
  if (status === "error") {
    return (
      <div className={containerClassName}>
        <p role="alert">Gagal memuat proses</p>
      </div>
    );
  }

  return (
    <div aria-live="polite" className={containerClassName}>
      <p className="whitespace-pre-wrap">{content}</p>
    </div>
  );
}
