import type { ReactNode } from 'react'
import { statusBadgeClass } from '../../monitoringUi'

type StatusBadgeProps = {
    status: string
    label?: string
    className?: string
}

export function StatusBadge({ status, label, className = '' }: StatusBadgeProps) {
    return (
        <span className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${statusBadgeClass(status)} ${className}`.trim()}>
            {label ?? status}
        </span>
    )
}

type MetricCardProps = {
    title: string
    value: ReactNode
    subtitle?: ReactNode
    children?: ReactNode
    valueClassName?: string
}

export function MetricCard({
    title,
    value,
    subtitle,
    children,
    valueClassName = 'text-gray-900',
}: MetricCardProps) {
    return (
        <article className="rounded-xl border border-gray-200 bg-gray-50 p-4">
            <p className="text-xs uppercase tracking-[0.12em] text-gray-500">{title}</p>
            <div className={`mt-2 text-3xl font-bold ${valueClassName}`}>{value}</div>
            {subtitle ? <p className="text-sm text-gray-500">{subtitle}</p> : null}
            {children}
        </article>
    )
}

type GaugeMeterProps = {
    ariaLabel: string
    label: string
    valueText: string
    caption: string
    progressLength: number
    strokeColor: string
    valueClassName: string
}

export function GaugeMeter({
    ariaLabel,
    label,
    valueText,
    caption,
    progressLength,
    strokeColor,
    valueClassName,
}: GaugeMeterProps) {
    return (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
            <p className="text-xs uppercase tracking-[0.12em] text-gray-500">{label}</p>
            <div className="mt-2 flex items-center gap-3">
                <svg
                    viewBox="0 0 200 120"
                    className="h-24 w-28"
                    role="img"
                    aria-label={ariaLabel}
                    tabIndex={0}
                >
                    <path
                        d="M20 100 A80 80 0 0 1 180 100"
                        fill="none"
                        stroke="#e5e7eb"
                        strokeWidth="12"
                        strokeLinecap="round"
                    />
                    <path
                        d="M20 100 A80 80 0 0 1 180 100"
                        fill="none"
                        stroke={strokeColor}
                        strokeWidth="12"
                        strokeLinecap="round"
                        strokeDasharray={`${progressLength} 251.2`}
                    />
                </svg>
                <div>
                    <p className={`text-2xl font-bold ${valueClassName}`}>{valueText}</p>
                    <p className="text-xs text-gray-500">{caption}</p>
                </div>
            </div>
        </div>
    )
}

