import { useEffect, useRef } from 'react'

interface FintocConnectWidgetProps {
  onSuccess: (linkToken: string) => void
  onExit: () => void
}

declare global {
  interface Window {
    Fintoc?: {
      create: (options: {
        publicKey: string
        product: string
        holderType: string
        country: string
        onSuccess: (data: { link_token: string }) => void
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

export function FintocConnectWidget({ onSuccess, onExit }: FintocConnectWidgetProps) {
  const onSuccessRef = useRef(onSuccess)
  const onExitRef = useRef(onExit)

  useEffect(() => {
    onSuccessRef.current = onSuccess
    onExitRef.current = onExit
  })

  useEffect(() => {
    let widget: { open: () => void; destroy?: () => void } | null = null

    loadFintocScript()
      .then(() => {
        if (!window.Fintoc) return
        widget = window.Fintoc.create({
          publicKey: import.meta.env.VITE_FINTOC_PUBLIC_KEY ?? '',
          product: 'movements',
          holderType: 'individual',
          country: 'cl',
          onSuccess: (data: { link_token: string }) => onSuccessRef.current(data.link_token),
          onExit: () => onExitRef.current(),
          onError: () => onExitRef.current(),
        })
        widget.open()
      })
      .catch((err) => {
        console.error('[FintocLink]', err)
        onExitRef.current()
      })

    return () => {
      widget?.destroy?.()
    }
  }, [])

  return null
}
