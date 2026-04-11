export type ChangePasswordErrors = {
    currentPassword: string
    newPassword: string
    newPasswordConfirm: string
    form: string
}

export type ChangePasswordFormValues = {
    currentPassword: string
    newPassword: string
    newPasswordConfirm: string
}

export const EMPTY_CHANGE_PASSWORD_ERRORS: ChangePasswordErrors = {
    currentPassword: '',
    newPassword: '',
    newPasswordConfirm: '',
    form: '',
}

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
}: ChangePasswordFormValues): {
    isValid: boolean
    errors: ChangePasswordErrors
} {
    const errors: ChangePasswordErrors = {
        ...EMPTY_CHANGE_PASSWORD_ERRORS,
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

export function buildChangePasswordPayload({
    currentPassword,
    newPassword,
    newPasswordConfirm,
    refreshToken,
}: ChangePasswordFormValues & {
    refreshToken?: string | null
}) {
    return {
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
        refresh_token: refreshToken ?? undefined,
    }
}
