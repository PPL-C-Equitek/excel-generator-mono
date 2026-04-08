'use client'

import type { ComponentProps } from 'react'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { changePassword } from '@/lib/api'
import {
    clearAuthTokens,
    getStoredRefreshToken,
    getValidAccessToken,
} from '@/lib/auth'

type ChangePasswordErrors = {
    currentPassword: string
    newPassword: string
    newPasswordConfirm: string
    form: string
}

type FormSubmitEvent = Parameters<
    NonNullable<ComponentProps<'form'>['onSubmit']>
>[0]

const PASSWORD_RULE_MESSAGE =
    'Password must be at least 8 characters long and include a letter, a number, and a special character.'

function isStrongEnough(password: string): boolean {
    return (
        password.length >= 8 &&
        /[a-zA-Z]/.test(password) &&
        /\d/.test(password) &&
        /[^A-Za-z0-9]/.test(password)
    )
}

export function validateChangePasswordForm({
    newPassword,
    newPasswordConfirm,
}: {
    currentPassword: string
    newPassword: string
    newPasswordConfirm: string
}): {
    isValid: boolean
    errors: ChangePasswordErrors
} {
    const errors: ChangePasswordErrors = {
        currentPassword: '',
        newPassword: '',
        newPasswordConfirm: '',
        form: '',
    }

    if (!newPassword) {
        errors.newPassword = 'New password is required.'
    } else if (!isStrongEnough(newPassword)) {
        errors.newPassword = PASSWORD_RULE_MESSAGE
    }

    if (!newPasswordConfirm) {
        errors.newPasswordConfirm = 'Password confirmation is required.'
    } else if (newPassword !== newPasswordConfirm) {
        errors.newPasswordConfirm = 'Password confirmation does not match.'
    }

    return {
        isValid: !errors.newPassword && !errors.newPasswordConfirm,
        errors,
    }
}

export default function ChangePasswordPage() {
    const router = useRouter()
    const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [newPasswordConfirm, setNewPasswordConfirm] = useState('')
    const [errors, setErrors] = useState<ChangePasswordErrors>({
        currentPassword: '',
        newPassword: '',
        newPasswordConfirm: '',
        form: '',
    })
    const [isLoading, setIsLoading] = useState(false)
    const [successMessage, setSuccessMessage] = useState('')

    useEffect(() => {
        return () => {
            if (redirectTimerRef.current) {
                globalThis.clearTimeout(redirectTimerRef.current)
            }
        }
    }, [])

    const handleSubmit = async (event: FormSubmitEvent) => {
        event.preventDefault()

        const validationResult = validateChangePasswordForm({
            currentPassword,
            newPassword,
            newPasswordConfirm,
        })
        setErrors(validationResult.errors)
        if (!validationResult.isValid) return

        setIsLoading(true)
        setSuccessMessage('')
        setErrors((prev) => ({ ...prev, form: '' }))

        try {
            const accessToken = await getValidAccessToken()
            if (!accessToken) {
                router.replace('/login')
                return
            }

            const refreshToken = getStoredRefreshToken()
            const response = await changePassword(accessToken, {
                current_password: currentPassword,
                new_password: newPassword,
                new_password_confirm: newPasswordConfirm,
                refresh_token: refreshToken ?? undefined,
            })

            clearAuthTokens()
            setSuccessMessage(
                response.message ||
                    'Password changed successfully. Redirecting to login...'
            )
            redirectTimerRef.current = globalThis.setTimeout(() => {
                router.replace('/login')
            }, 1500)
        } catch (error: unknown) {
            setErrors((prev) => ({
                ...prev,
                form:
                    error instanceof Error
                        ? error.message
                        : 'Failed to change password.',
            }))
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="flex min-h-screen">
            <Sidebar activeMenu="change-password" />
            <main className="ml-56 flex flex-1 items-center justify-center bg-gray-50 px-8 py-12">
                <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-10 shadow-sm">
                    <div className="space-y-2 text-center">
                        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
                            Change Password
                        </h1>
                        <p className="text-sm leading-relaxed text-slate-600">
                            Update your password and we&apos;ll sign you out afterward for security.
                        </p>
                    </div>

                    {successMessage ? (
                        <div className="mt-8 rounded-xl border border-green-200 bg-green-50 px-5 py-4 text-sm text-green-700">
                            {successMessage}
                        </div>
                    ) : (
                        <form className="mt-8 space-y-5" onSubmit={handleSubmit} noValidate>
                            {errors.form && (
                                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                    {errors.form}
                                </div>
                            )}

                            <div>
                                <label htmlFor="currentPassword" className="mb-1 block text-sm font-medium text-slate-700">
                                    Current Password
                                </label>
                                <input
                                    id="currentPassword"
                                    type="password"
                                    value={currentPassword}
                                    onChange={(event) => setCurrentPassword(event.target.value)}
                                    className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-red-500"
                                />
                                <p className="mt-1 text-xs text-slate-500">
                                    Leave this blank if you signed in with Google only.
                                </p>
                                {errors.currentPassword && (
                                    <p className="mt-1 text-sm text-red-600">{errors.currentPassword}</p>
                                )}
                            </div>

                            <div>
                                <label htmlFor="newPassword" className="mb-1 block text-sm font-medium text-slate-700">
                                    New Password
                                </label>
                                <input
                                    id="newPassword"
                                    type="password"
                                    value={newPassword}
                                    onChange={(event) => setNewPassword(event.target.value)}
                                    className={`w-full rounded-xl border px-4 py-3 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-red-500 ${
                                        errors.newPassword ? 'border-red-300' : 'border-slate-300'
                                    }`}
                                />
                                {errors.newPassword && (
                                    <p className="mt-1 text-sm text-red-600">{errors.newPassword}</p>
                                )}
                            </div>

                            <div>
                                <label htmlFor="newPasswordConfirm" className="mb-1 block text-sm font-medium text-slate-700">
                                    Confirm New Password
                                </label>
                                <input
                                    id="newPasswordConfirm"
                                    type="password"
                                    value={newPasswordConfirm}
                                    onChange={(event) => setNewPasswordConfirm(event.target.value)}
                                    className={`w-full rounded-xl border px-4 py-3 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-red-500 ${
                                        errors.newPasswordConfirm ? 'border-red-300' : 'border-slate-300'
                                    }`}
                                />
                                {errors.newPasswordConfirm && (
                                    <p className="mt-1 text-sm text-red-600">
                                        {errors.newPasswordConfirm}
                                    </p>
                                )}
                            </div>

                            <button
                                type="submit"
                                disabled={isLoading}
                                className="inline-flex w-full items-center justify-center rounded-xl bg-red-700 px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {isLoading ? 'Updating Password...' : 'Change Password'}
                            </button>
                        </form>
                    )}
                </div>
            </main>
        </div>
    )
}
