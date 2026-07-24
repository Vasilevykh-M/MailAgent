import type { FormEvent } from 'react'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError, loginPayloadSchema } from '../../api'
import { Alert, Button, Card, Field, Input, ThemeSwitch } from '../../shared'
import { useAuth } from './useAuth'

import styles from './LoginPage.module.css'

type LoginLocationState = {
  from?: {
    pathname?: string
    search?: string
  }
}

type LoginFieldErrors = {
  username?: string
  password?: string
}

function redirectPath(state: unknown): string {
  const value = state as LoginLocationState
  const pathname = value?.from?.pathname
  const search = value?.from?.search ?? ''

  return pathname ? `${pathname}${search}` : '/'
}

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) {
    return 'Неверный username или password.'
  }

  return 'Не удалось выполнить вход. Проверьте доступность API.'
}

export function LoginPage() {
  const auth = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<LoginFieldErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const destination = redirectPath(location.state)

  if (auth.status === 'authenticated') {
    return <Navigate replace to={destination} />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setFieldErrors({})

    const parsedPayload = loginPayloadSchema.safeParse({
      password,
      username,
    })

    if (!parsedPayload.success) {
      const invalidFields = new Set(
        parsedPayload.error.issues.map((issue) => issue.path[0]),
      )

      setFieldErrors({
        password: invalidFields.has('password')
          ? 'Введите password.'
          : undefined,
        username: invalidFields.has('username')
          ? 'Введите username.'
          : undefined,
      })
      return
    }

    setIsSubmitting(true)

    try {
      await auth.login(parsedPayload.data)
      navigate(destination, { replace: true })
    } catch (loginError) {
      setError(loginErrorMessage(loginError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <Card
          className={styles.card}
          title="Вход в Mail Agent"
          description="Введите учётные данные Results API."
          actions={<ThemeSwitch />}
        >
          <form className={styles.form} noValidate onSubmit={handleSubmit}>
            {error && (
              <Alert tone="danger" title="Ошибка входа">
                {error}
              </Alert>
            )}

            <Field error={fieldErrors.username} label="Username">
              <Input
                autoComplete="username"
                autoFocus
                invalid={Boolean(fieldErrors.username)}
                onChange={(event) => {
                  setUsername(event.target.value)
                  setFieldErrors((current) => ({
                    ...current,
                    username: undefined,
                  }))
                }}
                value={username}
              />
            </Field>

            <Field error={fieldErrors.password} label="Password">
              <Input
                autoComplete="current-password"
                invalid={Boolean(fieldErrors.password)}
                onChange={(event) => {
                  setPassword(event.target.value)
                  setFieldErrors((current) => ({
                    ...current,
                    password: undefined,
                  }))
                }}
                type="password"
                value={password}
              />
            </Field>

            <div className={styles.actions}>
              <Button disabled={isSubmitting} type="submit" variant="secondary">
                {isSubmitting ? 'Вход...' : 'Войти'}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </main>
  )
}
