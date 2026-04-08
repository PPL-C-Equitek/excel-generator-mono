'use client'

import Navbar from '@/components/Navbar'
import HeroSection from '@/components/HeroSection'
import FeatureCard from '@/components/FeatureCard'
import {
    LANDING_FEATURES,
    LANDING_NAV_LINKS,
    LANDING_HERO_CONFIG,
} from '@/constants/landing'

export default function LandingPage() {
    return (
        <div className="force-light min-h-screen flex flex-col"
            style={{
                colorScheme: 'light',
                backgroundColor: 'var(--background)',
                color: 'var(--foreground)',
            }}>
            <Navbar
                links={LANDING_NAV_LINKS}
                brandName="EQUITEK"
                activePage="home"
            />
            <HeroSection
                heading={LANDING_HERO_CONFIG.heading}
                subtitle={LANDING_HERO_CONFIG.subtitle}
                backgroundImage={LANDING_HERO_CONFIG.backgroundImage}
            />

            {/* Features Section */}
            <section className="py-20 px-8">
                <h2
                    className="text-3xl font-extrabold text-center mb-12 tracking-tight"
                    style={{ color: 'var(--foreground)' }}
                >
                    Why Use Our Service?
                </h2>
                <div
                    data-testid="features-grid"
                    className="grid grid-cols-1 gap-8 lg:grid-cols-3 max-w-5xl mx-auto">
                    {LANDING_FEATURES.map((feature) => (
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
