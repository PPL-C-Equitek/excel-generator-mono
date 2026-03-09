interface HeroSectionProps {
    readonly heading?: string
    readonly subtitle?: string
    readonly backgroundImage?: string
}

export default function HeroSection({
    heading = 'Automated Intelligence for Seamless Unstructured Data Transformation',
    subtitle = 'Empowering your workflow with traceable AI extraction and seamless Excel template mapping.',
    backgroundImage = '/hero-bg.png',
}: HeroSectionProps) {
    return (
        <section
            data-testid="hero-section"
            className="relative h-[600px] flex items-center"
            style={{
                backgroundImage: `url('${backgroundImage}')`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                backgroundColor: 'var(--surface-2)', // fallback jika gambar belum ada
            }}
        >
            {/* Dark overlay */}
            <div
                data-testid="hero-overlay"
                className="absolute inset-0"
                style={{ backgroundColor: 'rgba(0,0,0,0.60)' }}
            />

            {/* Content */}
            <div className="relative z-10 px-16 max-w-4xl">
                <h1 className="text-white font-extrabold text-5xl leading-tight mb-6 tracking-tight">
                    {heading}
                </h1>
                <p className="text-white text-lg font-medium max-w-xl leading-relaxed">
                    {subtitle}
                </p>
            </div>
        </section>
    )
}