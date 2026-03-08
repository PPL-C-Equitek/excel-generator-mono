import Navbar from '@/components/Navbar'
import HeroSection from '@/components/HeroSection'

const FEATURES = [
    {
        title: 'Advanced AI Transformation',
        desc: 'Leverage advanced LLMs to accurately interpret unstructured data',
    },
    {
        title: 'Instance Excel Mapping',
        desc: 'Maps messy data into your Excel template automatically.',
    },
    {
        title: 'Verified Logic',
        desc: 'Multi-step CoT to reduce errors and preserves data integrity.',
    },
    {
        title: 'Full Traceability',
        desc: 'Each extraction decision is recorded for accountability.',
    },
    {
        title: 'Consultant-Grade Standards',
        desc: 'Focused on professional methods and strong technical documentation.',
    },
    {
        title: 'Seamless Automation',
        desc: 'Replaces slow manual data entry with a ready-to-use automated workflow.',
    },
]

export default function LandingPage() {
    return (
        <div className="min-h-screen flex flex-col">
            <Navbar />
            <HeroSection />

            {/* Features Section */}
            <section className="py-20 px-8">
                <h2 className="text-3xl font-extrabold text-center text-gray-900 mb-12">
                    Why Use Our Service?
                </h2>
                <div className="grid grid-cols-3 gap-8 max-w-5xl mx-auto">
                    {FEATURES.map((feature) => (
                        <div key={feature.title} className="flex gap-4">
                            <div className="w-10 h-10 bg-red-100 rounded-lg flex-shrink-0" />
                            <div>
                                <h3 className="font-bold text-gray-900 text-sm mb-1">
                                    {feature.title}
                                </h3>
                                <p className="text-gray-500 text-sm">{feature.desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* CTA Section */}
            <section className="py-12 text-center">
                <h2 className="text-xl font-bold text-gray-900 mb-6">
                    Ready to Automate Your Data Workflow?
                </h2>
                <a
                    href="/convert"
                    className="bg-red-700 text-white font-bold px-8 py-3 rounded hover:bg-red-800 transition"
                >
                    Get Started
                </a>
            </section>

            {/* Footer */}
            <footer className="mt-auto px-8 py-6 flex justify-between items-center border-t border-gray-200">
                <p className="text-gray-500 text-sm">© Equitek. All rights reserved.</p>
                <a href="/privacy" className="text-gray-500 text-sm hover:underline">
                    Privacy Policy
                </a>
            </footer>
        </div>
    )
}