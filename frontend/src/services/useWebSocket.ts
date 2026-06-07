import { useRef, useCallback, useEffect, useState } from 'react'

/**
 * WebSocket message types sent by the server.
 */
export interface WSStreamStart {
  type: 'stream_start'
  step: string | null
  visit_id: string
}
export interface WSStreamToken {
  type: 'stream_token'
  token: string
}
export interface WSStreamEnd {
  type: 'stream_end'
  message: string
  current_step: string | null
  visit_id: string
  patient_id: number | null
  emergency_flag: boolean
  emergency_reason: string | null
  state: Record<string, any>
}
export interface WSError {
  type: 'error'
  message: string
}
export interface WSAuthOk {
  type: 'auth_ok'
  user_id: number
  patient_id: number
}
export interface WSPong {
  type: 'pong'
}

export type WSServerMessage =
  | WSStreamStart
  | WSStreamToken
  | WSStreamEnd
  | WSError
  | WSAuthOk
  | WSPong

export type ConnectionStatus = 'disconnected' | 'connecting' | 'authenticating' | 'connected' | 'reconnecting' | 'error'

interface UseWebSocketOptions {
  /** Called for every streamed token (partial text). */
  onToken?: (token: string) => void
  /** Called when the full response is ready. */
  onStreamEnd?: (data: WSStreamEnd) => void
  /** Called when streaming begins for a new agent step. */
  onStreamStart?: (data: WSStreamStart) => void
  /** Called on errors from the server. */
  onError?: (message: string) => void
  /** Called when reconnection succeeds. */
  onReconnect?: () => void
  /** Maximum number of reconnection attempts (default: 5). */
  maxReconnectAttempts?: number
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Reconnect config
const BASE_DELAY_MS = 1000     // 1 second initial delay
const MAX_DELAY_MS = 30_000    // 30 seconds max delay
const JITTER_FACTOR = 0.3     // ±30% randomisation

function httpToWs(url: string): string {
  return url.replace(/^http/, 'ws')
}

/** Calculate exponential backoff delay with jitter. */
function getBackoffDelay(attempt: number): number {
  const exponential = Math.min(BASE_DELAY_MS * Math.pow(2, attempt), MAX_DELAY_MS)
  const jitter = exponential * JITTER_FACTOR * (Math.random() * 2 - 1)
  return Math.round(exponential + jitter)
}

/**
 * React hook that manages a WebSocket connection to the diagnostic
 * streaming endpoint with automatic reconnection and exponential backoff.
 *
 * Features:
 * - Auto-reconnect on unexpected disconnection (up to maxReconnectAttempts)
 * - Exponential backoff with jitter to avoid thundering herd
 * - Keep-alive pings every 25s
 * - Graceful fallback to REST when WS is unavailable
 *
 * Usage:
 * ```ts
 * const { sendChat, status } = useWebSocket({
 *   onToken: (t) => appendToCurrentMessage(t),
 *   onStreamEnd: (d) => finaliseMessage(d),
 *   onReconnect: () => console.log('Reconnected!'),
 * })
 * ```
 */
export function useWebSocket(opts: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const optsRef = useRef(opts)
  optsRef.current = opts

  // Reconnection state
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalCloseRef = useRef(false)
  const maxAttempts = opts.maxReconnectAttempts ?? 5

  // Ping interval to keep connection alive
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearTimers = useCallback(() => {
    if (pingRef.current) {
      clearInterval(pingRef.current)
      pingRef.current = null
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  const cleanup = useCallback(() => {
    clearTimers()
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.onmessage = null
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close()
      }
      wsRef.current = null
    }
  }, [clearTimers])

  /** Internal connect logic (used for both initial connect and reconnect). */
  const connectInternal = useCallback((isReconnect: boolean = false) => {
    const token = localStorage.getItem('token')
    if (!token) {
      setStatus('error')
      optsRef.current.onError?.('No authentication token found. Please log in.')
      return
    }

    cleanup()
    setStatus(isReconnect ? 'reconnecting' : 'connecting')

    const wsUrl = `${httpToWs(API_BASE_URL)}/diagnostic/ws`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    intentionalCloseRef.current = false

    ws.onopen = () => {
      setStatus('authenticating')
      ws.send(JSON.stringify({ token }))
    }

    ws.onmessage = (event) => {
      let data: WSServerMessage
      try {
        data = JSON.parse(event.data)
      } catch {
        return
      }

      switch (data.type) {
        case 'auth_ok':
          setStatus('connected')
          // Reset reconnect counter on successful auth
          reconnectAttemptRef.current = 0
          if (isReconnect) {
            optsRef.current.onReconnect?.()
          }
          // Start keep-alive pings every 25s
          pingRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping' }))
            }
          }, 25_000)
          break

        case 'stream_start':
          optsRef.current.onStreamStart?.(data)
          break

        case 'stream_token':
          optsRef.current.onToken?.(data.token)
          break

        case 'stream_end':
          optsRef.current.onStreamEnd?.(data)
          break

        case 'error':
          if (data.message && !data.message.includes('Unknown message type')) {
            optsRef.current.onError?.(data.message)
          }
          break

        case 'pong':
          break
      }
    }

    ws.onerror = () => {
      // onerror is always followed by onclose, so reconnect logic lives there
    }

    ws.onclose = (event) => {
      if (pingRef.current) {
        clearInterval(pingRef.current)
        pingRef.current = null
      }

      // Don't reconnect if intentionally closed or auth rejected (code 1008)
      if (intentionalCloseRef.current || event.code === 1008) {
        setStatus('disconnected')
        return
      }

      // Attempt reconnect with exponential backoff
      const attempt = reconnectAttemptRef.current
      if (attempt < maxAttempts) {
        const delay = getBackoffDelay(attempt)
        reconnectAttemptRef.current = attempt + 1
        setStatus('reconnecting')
        console.log(
          `[WebSocket] Connection lost. Reconnecting in ${delay}ms (attempt ${attempt + 1}/${maxAttempts})...`
        )
        reconnectTimerRef.current = setTimeout(() => {
          connectInternal(true)
        }, delay)
      } else {
        // Exhausted all retries
        setStatus('error')
        optsRef.current.onError?.(
          `WebSocket disconnected after ${maxAttempts} reconnection attempts. Using REST fallback.`
        )
      }
    }
  }, [cleanup, clearTimers, maxAttempts])

  /** Public connect — resets attempt counter and starts fresh. */
  const connect = useCallback(() => {
    reconnectAttemptRef.current = 0
    connectInternal(false)
  }, [connectInternal])

  /** Send a chat message over the WebSocket. */
  const sendChat = useCallback(
    (message: string, visitId: string, xrayBase64?: string) => {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        optsRef.current.onError?.('WebSocket is not connected.')
        return false
      }
      const payload: Record<string, any> = {
        type: 'chat',
        message,
        visit_id: visitId,
      }
      if (xrayBase64) {
        payload.xray_base64 = xrayBase64
      }
      ws.send(JSON.stringify(payload))
      return true
    },
    [],
  )

  /** Gracefully disconnect — will NOT trigger reconnect. */
  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true
    reconnectAttemptRef.current = 0
    cleanup()
    setStatus('disconnected')
  }, [cleanup])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true
      cleanup()
    }
  }, [cleanup])

  return { connect, disconnect, sendChat, status }
}
