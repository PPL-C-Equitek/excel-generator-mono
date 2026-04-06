'use client'

import CustomSchemaManager from '@/components/CustomSchemaManager'
import Sidebar from '@/components/Sidebar'

export default function SchemaPage() {
    return (
        <div className="flex min-h-screen">
            <Sidebar activeMenu="schema" username="Username" />
            <main className="ml-56 flex flex-1 flex-col items-center justify-start bg-gray-50 px-16 py-12">
                <h1 className="mb-3 text-2xl font-bold text-gray-900">
                    Manage Your Custom Schemas
                </h1>
                <p className="mb-8 max-w-2xl text-center text-gray-500">
                    Review your saved mappings and add new ones without leaving this page.
                </p>
                <div className="w-full max-w-4xl">
                    <CustomSchemaManager />
                </div>
            </main>
        </div>
    )
}
