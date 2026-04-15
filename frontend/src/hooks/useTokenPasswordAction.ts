import { useCallback, useEffect, useState } from 'react';
import type { ComponentProps } from 'react';

type ActionStatus = 'form' | 'loading' | 'success' | 'error';

export type TokenFormErrors = {
  password: string;
  passwordConfirm: string;
};

export type TokenPasswordActionEvent = Parameters<
  NonNullable<ComponentProps<'form'>['onSubmit']>
>[0];

type UseTokenPasswordActionParams = {
  token: string | null;
  endpointPath: string;
  validateEndpointPath?: string;
  suspenseMessage: string;
  missingTokenMessage: string;
  invalidTokenMessage: string;
  unknownErrorMessage: string;
  loadingMessage: string;
  successFallbackMessage: string;
};

type UseTokenPasswordActionState = {
  status: ActionStatus;
  message: string;
  password: string;
  passwordConfirm: string;
  errors: TokenFormErrors;
  setPassword: (value: string) => void;
  setPasswordConfirm: (value: string) => void;
  handleSubmit: (event: TokenPasswordActionEvent) => Promise<void>;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function readFirstError(
  errors: Record<string, unknown>,
  field: 'password' | 'password_confirm'
): string {
  const value = errors[field];
  if (!Array.isArray(value)) {
    return '';
  }

  const firstError = value[0];
  return typeof firstError === 'string' ? firstError : '';
}

function hasFormErrors(errors: TokenFormErrors): boolean {
  return Boolean(errors.password || errors.passwordConfirm);
}

function readMessageFromResponse(data: unknown, fallback: string): string {
  return isRecord(data) && typeof data.message === 'string'
    ? data.message
    : fallback;
}

function readFieldErrors(data: unknown): TokenFormErrors | null {
  const errorMap = isRecord(data) ? data.errors : null;
  if (!isRecord(errorMap)) {
    return null;
  }

  const nextErrors = {
    password: readFirstError(errorMap, 'password'),
    passwordConfirm: readFirstError(errorMap, 'password_confirm'),
  };

  return hasFormErrors(nextErrors) ? nextErrors : null;
}

function validatePasswordForm(password: string, passwordConfirm: string): TokenFormErrors {
  const nextErrors: TokenFormErrors = {
    password: '',
    passwordConfirm: '',
  };

  if (!password) {
    nextErrors.password = 'Password is required.';
  }

  if (!passwordConfirm) {
    nextErrors.passwordConfirm = 'Password confirmation is required.';
  } else if (password !== passwordConfirm) {
    nextErrors.passwordConfirm = 'Passwords do not match.';
  }

  return nextErrors;
}

async function submitTokenPasswordAction(
  endpointPath: string,
  token: string | null,
  password: string,
  passwordConfirm: string
): Promise<Response> {
  return fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}${endpointPath}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      token,
      password,
      password_confirm: passwordConfirm,
    }),
  });
}

async function validateTokenAction(
  endpointPath: string,
  token: string
): Promise<Response> {
  return fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}${endpointPath}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      token,
    }),
  });
}

export function useTokenPasswordAction({
  token,
  endpointPath,
  validateEndpointPath,
  suspenseMessage,
  missingTokenMessage,
  invalidTokenMessage,
  unknownErrorMessage,
  loadingMessage,
  successFallbackMessage,
}: UseTokenPasswordActionParams): UseTokenPasswordActionState {
  const [status, setStatus] = useState<ActionStatus>(
    validateEndpointPath ? 'loading' : 'form'
  );
  const [message, setMessage] = useState(
    validateEndpointPath ? suspenseMessage : ''
  );
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [errors, setErrors] = useState<TokenFormErrors>({
    password: '',
    passwordConfirm: '',
  });

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage(missingTokenMessage);
    }
  }, [missingTokenMessage, token]);

  useEffect(() => {
    if (!validateEndpointPath || !token) {
      return;
    }

    let isCancelled = false;

    const checkTokenValidity = async () => {
      setStatus('loading');
      setMessage(suspenseMessage);

      try {
        const response = await validateTokenAction(validateEndpointPath, token);
        const data = await response.json().catch(() => null);

        if (!response.ok) {
          throw new Error(readMessageFromResponse(data, invalidTokenMessage));
        }

        if (!isCancelled) {
          setStatus('form');
          setMessage('');
        }
      } catch (error: unknown) {
        if (!isCancelled) {
          setStatus('error');
          setMessage(
            error instanceof Error ? error.message : unknownErrorMessage
          );
        }
      }
    };

    void checkTokenValidity();

    return () => {
      isCancelled = true;
    };
  }, [
    invalidTokenMessage,
    suspenseMessage,
    token,
    unknownErrorMessage,
    validateEndpointPath,
  ]);

  const handleSubmit = useCallback(
    async (event: TokenPasswordActionEvent): Promise<void> => {
      event.preventDefault();

      const nextErrors = validatePasswordForm(password, passwordConfirm);
      setErrors(nextErrors);
      if (hasFormErrors(nextErrors)) {
        return;
      }

      setStatus('loading');
      setMessage(loadingMessage);

      try {
        const response = await submitTokenPasswordAction(
          endpointPath,
          token,
          password,
          passwordConfirm
        );
        const data = await response.json().catch(() => null);
        const fieldErrors = response.status === 400 ? readFieldErrors(data) : null;

        if (fieldErrors) {
          setErrors(fieldErrors);
          setStatus('form');
          return;
        }

        if (!response.ok) {
          throw new Error(readMessageFromResponse(data, invalidTokenMessage));
        }

        setStatus('success');
        setMessage(readMessageFromResponse(data, successFallbackMessage));
      } catch (error: unknown) {
        setStatus('error');
        setMessage(error instanceof Error ? error.message : unknownErrorMessage);
      }
    },
    [
      endpointPath,
      invalidTokenMessage,
      loadingMessage,
      password,
      passwordConfirm,
      successFallbackMessage,
      token,
      unknownErrorMessage,
    ]
  );

  return {
    status,
    message,
    password,
    passwordConfirm,
    errors,
    setPassword: (value) => setPassword(value),
    setPasswordConfirm: (value) => setPasswordConfirm(value),
    handleSubmit,
  };
}
