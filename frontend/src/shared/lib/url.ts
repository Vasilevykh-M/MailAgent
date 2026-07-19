export function toAbsoluteApiUrl(path: string, baseUrl: string): string {
  return new URL(path, baseUrl).toString()
}
