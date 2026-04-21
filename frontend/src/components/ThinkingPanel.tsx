type ThinkingPanelProps = {
  status: "idle" | "thinking" | "success" | "error";
  content: string;
};

export default function ThinkingPanel({ status, content }: ThinkingPanelProps) {
  return (
    <div className="max-h-[400px] overflow-y-auto rounded-md border border-gray-200 bg-white p-4">
      {status === "error" ? "Gagal memuat proses" : content}
    </div>
  );
}
