import { formatJson } from '../../lib'

import styles from './JsonViewer.module.css'

type JsonViewerProps = {
  value: unknown
}

export function JsonViewer({ value }: JsonViewerProps) {
  return <pre className={styles.viewer}>{formatJson(value)}</pre>
}
