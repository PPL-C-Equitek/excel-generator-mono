// "use client";

// import SessionDetail, { type Session } from "@/components/SessionDetail";

// const longOutput = `| model | score | latency |
// | ----- | ----- | ------- |
// | GPT-4.1 | 92.5 | 1.2s |
// | Claude | 90.1 | 1.1s |

// const extremelyLongToken = "${"benchmark_token_".repeat(48)}";

// ${Array.from({ length: 16 }, (_, index) =>
//   `Baris ${index + 1}: output panjang ini dipakai untuk memastikan container tetap aman, teks tetap terbaca, dan layout tidak overflow saat konten sangat besar.`
// ).join("\n")}`;

// const mockSession: Session = {
//   id: "session-001",
//   prompt: "Bandingkan performa GPT-4.1 dan Claude pada benchmark reasoning.",
//   score: 92.5,
//   evaluatedAt: "2026-04-22T09:30:00.000Z",
//   output: longOutput,
// };

// export default function SessionDetailSandboxPage() {
//   return (
//     <main className="min-h-screen bg-slate-50 px-4 py-10 sm:px-6 lg:px-8">
//       <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
//         <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
//           <p className="text-sm font-semibold uppercase tracking-[0.2em] text-red-700">
//             Sandbox
//           </p>
//           <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
//             SessionDetail Manual Test
//           </h1>
//           <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
//             Halaman ini dipakai untuk mengecek render data session, state not
//             found, dan perilaku overflow untuk output yang sangat panjang.
//           </p>
//         </header>

//         <section className="grid gap-6 lg:grid-cols-2">
//           <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
//             <h2 className="text-lg font-semibold text-slate-900">Valid Session Preview</h2>
//             <p className="mt-2 text-sm text-slate-500">
//               Pastikan semua field tampil dan area output tidak merusak layout.
//             </p>

//             <div className="mt-6">
//               <SessionDetail session={mockSession} isNotFound={false} />
//             </div>
//           </section>

//           <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
//             <h2 className="text-lg font-semibold text-slate-900">Not Found Preview</h2>
//             <p className="mt-2 text-sm text-slate-500">
//               Pastikan pesan fallback tampil jelas ketika data session tidak ada.
//             </p>

//             <div className="mt-6">
//               <SessionDetail session={null} isNotFound />
//             </div>
//           </section>
//         </section>
//       </div>
//     </main>
//   );
// }
