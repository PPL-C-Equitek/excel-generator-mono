export const LOGIN_EMAIL_PATTERN =
    /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+$/

export const LOGIN_EMAIL_MAX_LENGTH = 254
export const LOGIN_EMAIL_ERROR_MESSAGE = 'Please enter a valid email address.'
export const LOGIN_PASSWORD_REQUIRED_MESSAGE = 'Password is required.'

interface LoginValidationData {
    email: string
    password: string
}

export function getLoginValidationError({ email, password }: LoginValidationData) {
    if (!email || email.length > LOGIN_EMAIL_MAX_LENGTH || !LOGIN_EMAIL_PATTERN.test(email)) {
        return LOGIN_EMAIL_ERROR_MESSAGE
    }

    if (!password.trim()) {
        return LOGIN_PASSWORD_REQUIRED_MESSAGE
    }

    return null
}
