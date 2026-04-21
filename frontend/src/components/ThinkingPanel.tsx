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
      <section aria-live="polite" className={containerClassName}>
        <p role="alert">Gagal memuat proses</p>
      </section>
    );
  }

  return (
    <section aria-live="polite" className={containerClassName}>
      <p>{content}</p>
    </section>
  );
}
