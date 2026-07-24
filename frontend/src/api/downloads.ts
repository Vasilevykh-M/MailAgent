import { clearStoredAuthToken } from './authToken'
import { buildApiHeaders, getAbsoluteApiUrl } from './client'
import { parseApiError } from './errors'

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')

  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function filenameFromContentDisposition(value: string | null) {
  if (!value) {
    return null
  }

  const utfMatch = /filename\*=UTF-8''([^;]+)/i.exec(value)
  if (utfMatch?.[1]) {
    return decodeURIComponent(utfMatch[1])
  }

  const asciiMatch = /filename="?([^";]+)"?/i.exec(value)

  return asciiMatch?.[1] ?? null
}

export async function downloadBlobFromApiPath(
  path: string,
  fallbackFilename: string,
) {
  const response = await fetch(getAbsoluteApiUrl(path), {
    headers: buildApiHeaders({ acceptJson: false }),
  })

  if (!response.ok) {
    const error = await parseApiError(response)

    if (error.status === 401) {
      clearStoredAuthToken()
    }

    throw error
  }

  const blob = await response.blob()
  const filename =
    filenameFromContentDisposition(
      response.headers.get('Content-Disposition'),
    ) ?? fallbackFilename

  triggerBrowserDownload(blob, filename)
}

export function downloadAttachment(path: string, fallbackFilename: string) {
  return downloadBlobFromApiPath(path, fallbackFilename)
}

export function downloadRawEmail(path: string) {
  return downloadBlobFromApiPath(path, 'message.eml')
}
