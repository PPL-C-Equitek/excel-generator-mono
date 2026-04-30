// "use client";

// import { useEffect, useRef, useState } from "react";
// import ThinkingPanel from "@/components/ThinkingPanel";
// import type { ThinkingPanelProps } from "@/components/ThinkingPanel";

// const SAMPLE_STREAM = [
//   "Memproses benchmark request...",
//   "Menyusun langkah reasoning model...",
//   "Membandingkan latency dan kualitas output...",
//   "Menyelesaikan ringkasan thinking process.",
// ];

// const LONG_TEXT = Array.from({ length: 40 }, (_, index) =>
//   `Baris ${index + 1}: model sedang menuliskan reasoning yang cukup panjang untuk menguji stabilitas container.`
// ).join("\n");

// export default function ThinkingPanelSandboxPage() {
//   const [status, setStatus] = useState<ThinkingPanelProps["status"]>("idle");
//   const [content, setContent] = useState("Thinking panel preview akan tampil di sini.");
//   const intervalRef = useRef<number | null>(null);

//   useEffect(() => {
//     return () => {
//       if (intervalRef.current !== null) {
//         window.clearInterval(intervalRef.current);
//       }
//     };
//   }, []);

//   const stopStreaming = () => {
//     if (intervalRef.current !== null) {
//       window.clearInterval(intervalRef.current);
//       intervalRef.current = null;
//     }
//   };

//   const startStreamingDemo = () => {
//     stopStreaming();
//     setStatus("thinking");
//     setContent("");

//     let index = 0;

//     intervalRef.current = window.setInterval(() => {
//       if (index >= SAMPLE_STREAM.length) {
//         stopStreaming();
//         setStatus("success");
//         return;
//       }

//       setContent((current) =>
//         current ? `${current}\n${SAMPLE_STREAM[index]}` : SAMPLE_STREAM[index]
//       );

//       index += 1;
//     }, 700);
//   };

//   return (
//     <main className="min-h-screen bg-slate-50 px-4 py-10 sm:px-6 lg:px-8">
//       <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
//         <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
//           <p className="text-sm font-semibold uppercase tracking-[0.2em] text-red-700">
//             Sandbox
//           </p>
//           <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
//             ThinkingPanel Manual Test
//           </h1>
//           <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
//             Pakai halaman ini untuk cek rendering stream, state error, dan
//             perilaku kontainer saat menerima teks yang sangat panjang.
//           </p>
//         </header>

//         <section className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
//           <aside className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
//             <h2 className="text-lg font-semibold text-slate-900">Control Panel</h2>

//             <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="status">
//               Status
//             </label>
//             <select
//               id="status"
//               className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-200"
//               value={status}
//               onChange={(event) => setStatus(event.target.value as ThinkingPanelProps["status"])}
//             >
//               <option value="idle">idle</option>
//               <option value="thinking">thinking</option>
//               <option value="success">success</option>
//               <option value="error">error</option>
//             </select>

//             <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="content">
//               Content
//             </label>
//             <textarea
//               id="content"
//               className="mt-2 min-h-56 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-200"
//               value={content}
//               onChange={(event) => setContent(event.target.value)}
//             />

//             <div className="mt-5 grid gap-3">
//               <button
//                 type="button"
//                 className="rounded-xl bg-red-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-600 focus:ring-2 focus:ring-red-200 focus:outline-none"
//                 onClick={startStreamingDemo}
//               >
//                 Start Stream Demo
//               </button>
//               <button
//                 type="button"
//                 className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-900 transition hover:bg-slate-50 focus:ring-2 focus:ring-blue-200 focus:outline-none"
//                 onClick={() => {
//                   stopStreaming();
//                   setStatus("thinking");
//                   setContent(LONG_TEXT);
//                 }}
//               >
//                 Load Long Text
//               </button>
//               <button
//                 type="button"
//                 className="rounded-xl border border-red-300 bg-red-50 px-4 py-2.5 text-sm font-semibold text-red-700 transition hover:bg-red-100 focus:ring-2 focus:ring-red-200 focus:outline-none"
//                 onClick={() => {
//                   stopStreaming();
//                   setStatus("error");
//                 }}
//               >
//                 Trigger Error State
//               </button>
//               <button
//                 type="button"
//                 className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-900 transition hover:bg-slate-50 focus:ring-2 focus:ring-blue-200 focus:outline-none"
//                 onClick={() => {
//                   stopStreaming();
//                   setStatus("idle");
//                   setContent("Thinking panel preview akan tampil di sini.");
//                 }}
//               >
//                 Reset
//               </button>
//             </div>

//             <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
//               <p className="font-semibold text-slate-900">Checklist manual</p>
//               <ul className="mt-2 space-y-2">
//                 <li>Ubah ke `thinking` lalu pastikan teks tampil normal.</li>
//                 <li>Klik `Trigger Error State` lalu cek pesan error spesifik.</li>
//                 <li>Klik `Load Long Text` lalu pastikan area bisa di-scroll.</li>
//               </ul>
//             </div>
//           </aside>

//           <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
//             <div className="flex items-center justify-between gap-3 border-b border-slate-200 pb-4">
//               <div>
//                 <h2 className="text-lg font-semibold text-slate-900">Preview</h2>
//                 <p className="text-sm text-slate-500">
//                   Current status: <span className="font-medium text-slate-900">{status}</span>
//                 </p>
//               </div>
//             </div>

//             <div className="mt-6">
//               <ThinkingPanel status={status} content={content} />
//             </div>
//           </section>
//         </section>
//       </div>
//     </main>
//   );
// }
