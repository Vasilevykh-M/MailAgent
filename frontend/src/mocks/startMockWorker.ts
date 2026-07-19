export async function startMockWorker() {
  if (
    !import.meta.env.DEV ||
    import.meta.env.VITE_ENABLE_API_MOCKS === 'false'
  ) {
    return
  }

  const { worker } = await import('./browser')

  await worker.start({
    onUnhandledRequest: 'bypass',
    serviceWorker: {
      url: '/mockServiceWorker.js',
    },
  })
}
