import { useEffect, useRef } from 'react'
import { getFintoc } from '@fintoc/fintoc-js'

interface FintocConnectWidgetProps {
  onSuccess: (linkToken: string) => void
  onExit: () => void
}

export function FintocConnectWidget({ onSuccess, onExit }: FintocConnectWidgetProps) {
  const onSuccessRef = useRef(onSuccess)
  const onExitRef = useRef(onExit)

  useEffect(() => {
    onSuccessRef.current = onSuccess
    onExitRef.current = onExit
  })

  useEffect(() => {
    let active = true
    let widget: { open: () => void; destroy?: () => void } | null = null

    getFintoc()
      .then((Fintoc) => {
        if (!active || !Fintoc) return
        const pubKey = import.meta.env.VITE_FINTOC_PUBLIC_KEY ?? ''
        const webhookUrl = import.meta.env.VITE_FINTOC_WEBHOOK_URL || 'https://webhook.securo.com'

        console.log('[FintocLink] Initializing widget with publicKey:', pubKey, 'and webhookUrl:', webhookUrl)
        if (!pubKey) {
          console.warn('[FintocLink] WARNING: VITE_FINTOC_PUBLIC_KEY is undefined or empty!')
        }

        widget = Fintoc.create({
          publicKey: pubKey,
          product: 'movements',
          holderType: 'individual',
          country: 'cl',
          webhookUrl,
          onSuccess: (data: any) => {
            // Fintoc passes a link object where token/link_token contains the link_token
            const token = data?.token || data?.link_token
            if (token) {
              onSuccessRef.current(token)
            } else {
              console.error('[FintocLink] Failed to find link token in onSuccess payload:', data)
              onExitRef.current()
            }
          },
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
      active = false
      widget?.destroy?.()
    }
  }, [])

  return null
}

