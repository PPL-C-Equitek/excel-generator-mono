import type { CSSProperties } from 'react'

export type FeedbackVariant = 'success' | 'warning' | 'error' | 'info'

interface FeedbackStyle {
    role: 'status' | 'alert'
    label: string
    icon: React.ReactNode
    styles: CSSProperties
}

interface FeedbackMessageProps {
    message: string
    variant?: FeedbackVariant
    className?: string
    dismissible?: boolean
    onDismiss?: () => void
}

const CheckIcon = () => (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <circle cx="9" cy="9" r="8" stroke="currentColor" strokeWidth="1.5" />
        <polyline points="5.5,9 7.8,11.5 12.5,6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
)

const WarnIcon = () => (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <path d="M9 2L16.5 15.5H1.5L9 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <line x1="9" y1="7" x2="9" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="9" cy="13.5" r="0.75" fill="currentColor" />
    </svg>
)

const ErrorIcon = () => (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <circle cx="9" cy="9" r="8" stroke="currentColor" strokeWidth="1.5" />
        <line x1="6" y1="6" x2="12" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="12" y1="6" x2="6" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
)

const InfoIcon = () => (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <circle cx="9" cy="9" r="8" stroke="currentColor" strokeWidth="1.5" />
        <line x1="9" y1="8" x2="9" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="9" cy="5.5" r="0.75" fill="currentColor" />
    </svg>
)

const CloseIcon = () => (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
        <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
)

const FEEDBACK_STRATEGIES: Record<FeedbackVariant, FeedbackStyle> = {
    success: {
        role: 'status',
        label: 'Success',
        icon: <CheckIcon />,
        styles: {
            backgroundColor: 'var(--success-bg)',
            borderLeftColor: 'var(--success-border)',
            color: 'var(--success-text)',
        },
    },
    warning: {
        role: 'alert',
        label: 'Warning',
        icon: <WarnIcon />,
        styles: {
            backgroundColor: 'var(--warning-bg)',
            borderLeftColor: 'var(--warning-border)',
            color: 'var(--warning-text)',
        },
    },
    error: {
        role: 'alert',
        label: 'Error',
        icon: <ErrorIcon />,
        styles: {
            backgroundColor: 'var(--danger-bg)',
            borderLeftColor: 'var(--danger-border)',
            color: 'var(--danger-text)',
        },
    },
    info: {
        role: 'status',
        label: 'Info',
        icon: <InfoIcon />,
        styles: {
            backgroundColor: 'var(--info-bg)',
            borderLeftColor: 'var(--info-border)',
            color: 'var(--info-text)',
        },
    },
}

export default function FeedbackMessage({
    message,
    variant = 'info',
    className = '',
    dismissible = false,
    onDismiss,
}: Readonly<FeedbackMessageProps>) {
    const { role, label, icon, styles } = FEEDBACK_STRATEGIES[variant]

    return (
        <div
            role={role}
            className={`feedback-message ${variant} ${className}`.trim()}
            style={{
                ...styles,
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '14px 16px',
                borderRadius: '10px',
                borderLeft: '3px solid',
                animation: 'fb-in 0.25s cubic-bezier(.22,1,.36,1) both',
            }}
        >
            <span style={{ flexShrink: 0, marginTop: '1px' }}>{icon}</span>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', opacity: 0.75 }}>
                    {label}
                </span>
                <span style={{ fontSize: '14px', lineHeight: 1.5 }}>{message}</span>
            </div>

            {dismissible && (
                <button
                    onClick={onDismiss}
                    aria-label="Tutup pesan"
                    style={{ flexShrink: 0, width: 18, height: 18, opacity: 0.45, cursor: 'pointer', border: 'none', background: 'none', padding: 0, color: 'inherit' }}
                >
                    <CloseIcon />
                </button>
            )}
        </div>
    )
}