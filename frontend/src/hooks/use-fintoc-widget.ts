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

        widget = Fintoc.create({
          publicKey: import.meta.env.VITE_FINTOC_PUBLIC_KEY,
          product: 'movements',
          holderType: 'individual',
          country: 'cl',
          onSuccess: (data: { link_token: string }) => {
            if (data?.link_token) {
              onSuccessRef.current(data.link_token)
            } else {
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

