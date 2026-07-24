import { useNavigate } from 'react-router-dom'

import { Button } from '../../shared'
import { useAuth } from './useAuth'

import styles from './UserMenu.module.css'

export function UserMenu() {
  const auth = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await auth.logout()
    navigate('/login', { replace: true })
  }

  if (auth.status !== 'authenticated' || !auth.user) {
    return null
  }

  return (
    <>
      <span className={styles.user}>{auth.user.username}</span>
      <Button onClick={handleLogout} variant="ghost">
        Выйти
      </Button>
    </>
  )
}
