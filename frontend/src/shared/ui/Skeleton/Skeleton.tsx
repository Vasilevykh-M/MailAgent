import type { CSSProperties, ComponentPropsWithoutRef } from 'react'

import styles from './Skeleton.module.css'

type SkeletonProps = ComponentPropsWithoutRef<'div'> & {
  height?: CSSProperties['height']
  radius?: 'sm' | 'md'
  width?: CSSProperties['width']
}

export function Skeleton({
  className,
  height,
  radius = 'md',
  style,
  width,
  ...props
}: SkeletonProps) {
  const classNames = [styles.skeleton, styles[radius], className]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      aria-hidden="true"
      className={classNames}
      style={{ height, width, ...style }}
      {...props}
    />
  )
}
