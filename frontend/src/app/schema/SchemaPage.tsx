'use client'

import CustomSchemaManager from '@/components/CustomSchemaManager'
import Sidebar from '@/components/Sidebar'

export default function SchemaPage() {
    return (
        <div className="flex min-h-screen bg-gray-50">
            <Sidebar activeMenu="schema" />
            <main className="ml-56 flex-1 px-8 py-12">
                <div className="mx-auto w-full max-w-6xl space-y-8">
                    <section className="rounded-3xl border border-red-100 bg-white p-8 shadow-sm shadow-red-100/30">
                        <div className="space-y-3">
                            <span className="inline-flex rounded-full bg-red-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-red-700">
                                Schema Library
                            </span>
                            <h1 className="text-2xl font-bold text-slate-900">
                                Manage Your Custom Schemas
                            </h1>
                            <p className="max-w-4xl text-sm leading-relaxed text-slate-600">
                                Review your saved mappings, refine reusable output structures, and add
                                new schemas without leaving this page.
                            </p>
                        </div>
                    </section>

                    <div className="w-full">
                        <CustomSchemaManager />
                    </div>
                </div>
            </main>
        </div>
    )
}
