'use client'

import Sidebar from '@/components/Sidebar'
import UploadZone from '@/components/UploadZone'

export default function ConvertPage() {
    const handleFileSelect = (file: File) => {
        console.log('File selected:', file.name)
        // Lanjutkan ke logic API call
    }

    return (
        <div className="flex min-h-screen">
            <Sidebar activeMenu="convert" username="Username" />
            <main className="flex-1 bg-gray-50 flex flex-col items-center justify-center px-16">
                <h1 className="text-2xl font-bold text-gray-900 mb-3">
                    Automate Your Data Structuring
                </h1>
                <p className="text-gray-500 text-center mb-8 max-w-md">
                    Replace manual entry with AI-driven extraction and seamless Excel template mapping.
                </p>
                <div className="w-full max-w-3xl">
                    <UploadZone onFileSelect={handleFileSelect} />
                </div>
            </main>
        </div>
    )
}