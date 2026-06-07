import api from './api'
import { DiagnosticResponse, DiagnosticState } from './types'

export const diagnosticService = {
  /**
   * Start a new diagnostic session
   */
  start: async (): Promise<DiagnosticResponse> => {
    const response = await api.post<DiagnosticResponse>('/diagnostic/start')
    return response.data
  },

  /**
   * Send a message in the diagnostic chat
   */
  chat: async (
    message: string,
    visitId: string,
    xrayImage?: File,
    clientState?: Record<string, unknown> | null,
  ): Promise<DiagnosticResponse> => {
    const formData = new FormData()
    formData.append('message', message)
    formData.append('visit_id', visitId)

    if (clientState) {
      formData.append('client_state', JSON.stringify(clientState))
    }
    
    if (xrayImage) {
      formData.append('xray_image', xrayImage)
    }

    // Wrap the request with a client-side timeout to avoid the UI hanging indefinitely
    const timeoutMs = 30000 // 30 seconds

    const requestPromise = api.post<DiagnosticResponse>(
      '/diagnostic/chat',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )

    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('The system is taking longer than expected. Please try again.')), timeoutMs)
    )

    const response = await Promise.race([requestPromise, timeoutPromise]) as any
    return (response as { data: DiagnosticResponse }).data
  },

  /**
   * Get current state of a diagnostic session
   */
  getState: async (visitId: string): Promise<DiagnosticState> => {
    const response = await api.get<{ state: DiagnosticState }>(
      `/diagnostic/state/${visitId}`
    )
    return response.data.state
  },

  /**
   * Delete/clear a diagnostic session
   */
  deleteSession: async (visitId: string): Promise<void> => {
    await api.delete(`/diagnostic/delete/${visitId}`)
  },
}

