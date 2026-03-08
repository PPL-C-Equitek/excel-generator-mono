interface FeatureCardProps {
    title: string
    desc: string
    icon?: React.ReactNode
}

export default function FeatureCard({ title, desc, icon }: FeatureCardProps) {
    return (
        <div className="flex gap-4">
            <div
                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-sm"
                style={{
                    backgroundColor: 'var(--danger-bg)',
                    color: 'var(--brand-primary)',
                }}
            >
                {icon ?? '▪'}
            </div>
            <div>
                <h3 className="font-bold text-sm mb-1" style={{ color: 'var(--foreground)' }}>
                    {title}
                </h3>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    {desc}
                </p>
            </div>
        </div>
    )
}