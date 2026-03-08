'use client'

import Navbar from '@/components/Navbar'
import HeroSection from '@/components/HeroSection'
import FeatureCard from '@/components/FeatureCard'

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
        <div className="force-light min-h-screen flex flex-col"
            style={{
                colorScheme: 'light',
                backgroundColor: 'var(--background)',
                color: '#171717',
            }}>
            <Navbar />
            <HeroSection />

            {/* Features Section */}
            <section className="py-20 px-8">
                <h2
                    className="text-3xl font-extrabold text-center mb-12 tracking-tight"
                    style={{ color: 'var(--foreground)' }}
                >
                    Why Use Our Service?
                </h2>
                <div className="grid grid-cols-1 gap-8 lg:grid-cols-3 max-w-5xl mx-auto">
                    {FEATURES.map((feature) => (
                        <FeatureCard key={feature.title} {...feature} />
                    ))}
                </div>
            </section>

            {/* CTA Section */}
            <section className="py-12 text-center border-t" style={{ borderColor: 'var(--border-default)' }}>
                <h2
                    className="text-xl font-bold mb-6"
                    style={{ color: 'var(--foreground)' }}
                >
                    Ready to Automate Your Data Workflow?
                </h2>
                <a
                    href="/convert"
                    className="inline-block font-bold px-8 py-3 rounded-xl text-white transition active:scale-[0.98]"
                    style={{
                        backgroundColor: 'var(--brand-primary)',
                    }}
                    onMouseEnter={(e) =>
                        (e.currentTarget.style.backgroundColor = 'var(--brand-primary-hover)')
                    }
                    onMouseLeave={(e) =>
                        (e.currentTarget.style.backgroundColor = 'var(--brand-primary)')
                    }
                >
                    Get Started
                </a>
            </section>

            {/* Footer */}
            <footer
                className="mt-auto px-8 py-6 flex justify-between items-center border-t text-sm"
                style={{
                    borderColor: 'var(--border-default)',
                    color: 'var(--text-muted)',
                }}
            >
                <p>© Equitek. All rights reserved.</p>
                <a
                    href="/privacy"
                    className="hover:underline transition"
                    style={{ color: 'var(--text-muted)' }}
                >
                    Privacy Policy
                </a>
            </footer>
        </div>
    )
}