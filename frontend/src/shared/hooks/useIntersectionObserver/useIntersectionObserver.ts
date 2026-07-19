import { useCallback, useEffect, useState } from 'react'

type UseIntersectionObserverOptions = {
  rootMargin?: string
  threshold?: number
}

export function useIntersectionObserver<TElement extends Element>({
  rootMargin = '240px',
  threshold = 0,
}: UseIntersectionObserverOptions = {}) {
  const [target, setTarget] = useState<TElement | null>(null)
  const [isIntersecting, setIsIntersecting] = useState(false)
  const targetRef = useCallback((node: TElement | null) => {
    setTarget(node)
  }, [])

  useEffect(() => {
    if (!target) {
      setIsIntersecting(false)
      return
    }

    const observer = new IntersectionObserver(
      ([entry]) => setIsIntersecting(Boolean(entry?.isIntersecting)),
      { rootMargin, threshold },
    )

    observer.observe(target)

    return () => observer.disconnect()
  }, [rootMargin, target, threshold])

  return { isIntersecting, targetRef }
}
