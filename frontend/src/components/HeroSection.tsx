import { LANDING_HERO_CONFIG } from '@/constants/landing'

interface HeroSectionProps {
    readonly heading?: string
    readonly subtitle?: string
    readonly backgroundImage?: string
}

export default function HeroSection({
    heading,
    subtitle,
    backgroundImage,
}: HeroSectionProps) {
    const resolvedHeading = heading ?? LANDING_HERO_CONFIG.heading
    const resolvedSubtitle = subtitle ?? LANDING_HERO_CONFIG.subtitle
    const resolvedBg = backgroundImage ?? LANDING_HERO_CONFIG.backgroundImage

    return (
        <section
            data-testid="hero-section"
            className="relative h-[600px] flex items-center"
            style={{
                backgroundImage: `url('${resolvedBg}')`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                backgroundColor: 'var(--surface-2)',
            }}
        >
            <div
                data-testid="hero-overlay"
                className="absolute inset-0"
                style={{ backgroundColor: 'rgba(0,0,0,0.60)' }}
            />
            <div className="relative z-10 px-16 max-w-4xl">
                <h1 className="text-white font-extrabold text-5xl leading-tight mb-6 tracking-tight">
                    {resolvedHeading}
                </h1>
                <p className="text-white text-lg font-medium max-w-xl leading-relaxed">
                    {resolvedSubtitle}
                </p>
            </div>
        </section>
    )
}