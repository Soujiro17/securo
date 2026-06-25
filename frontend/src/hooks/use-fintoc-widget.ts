import { useEffect } from 'react'

interface FintocConnectWidgetProps {
  widgetToken: string
  onSuccess: (linkToken: string) => void
  onExit: () => void
}

declare global {
  interface Window {
    Fintoc?: {
      create: (options: {
        publicKey: string
        widgetToken: string
        product: string
        onSuccess: (data: { exchange_token: string }) => void
        onExit: () => void
        onError: () => void
      }) => { open: () => void; destroy?: () => void }
    }
  }
}

function loadFintocScript(): Promise<void> {
  if (window.Fintoc) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://js.fintoc.com/v1'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load FintocLink script'))
    document.head.appendChild(script)
  })
}

export function FintocConnectWidget({ widgetToken, onSuccess, onExit }: FintocConnectWidgetProps) {
  useEffect(() => {
    let widget: { open: () => void; destroy?: () => void } | null = null

    loadFintocScript()
      .then(() => {
        if (!window.Fintoc) return
        widget = window.Fintoc.create({
          publicKey: import.meta.env.VITE_FINTOC_PUBLIC_KEY ?? '',
          widgetToken,
          product: 'movements',
          onSuccess: ({ exchange_token }) => onSuccess(exchange_token),
          onExit,
          onError: onExit,
        })
        widget.open()
      })
      .catch((err) => {
        console.error('[FintocLink]', err)
        onExit()
      })

    return () => {
      widget?.destroy?.()
    }
  }, [widgetToken, onSuccess, onExit])

  return null
}
