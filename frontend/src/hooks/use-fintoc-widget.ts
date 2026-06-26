import { useEffect, useRef } from 'react'
import { getFintoc } from '@fintoc/fintoc-js'

interface FintocConnectWidgetProps {
  widgetToken: string
  onSuccess: (linkToken: string) => void
  onExit: () => void
}

export function FintocConnectWidget({ widgetToken, onSuccess, onExit }: FintocConnectWidgetProps) {
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

        console.log('[FintocLink] Initializing widget with widgetToken:', widgetToken)

        widget = Fintoc.create({
          publicKey: import.meta.env.VITE_FINTOC_PUBLIC_KEY,
          widgetToken,
          onSuccess: (data: any) => {
            const token = data?.exchange_token || data?.id || data?.token || data?.link_token || data?.link?.id
            if (token) {
              onSuccessRef.current(token)
            } else {
              console.error('[FintocLink] Failed to find link/exchange token in onSuccess payload:', data)
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

