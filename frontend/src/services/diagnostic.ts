import api from './api'
import { DiagnosticResponse, DiagnosticState } from './types'

const CHAT_TIMEOUT_MS = 180000

export const diagnosticService = {
  start: async (): Promise<DiagnosticResponse> => {
    const response = await api.post<DiagnosticResponse>('/diagnostic/start')
    return response.data
  },

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

    const response = await api.post<DiagnosticResponse>(
      '/diagnostic/chat',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: CHAT_TIMEOUT_MS,
      }
    )
    return response.data
  },

  getState: async (visitId: string): Promise<DiagnosticState> => {
    const response = await api.get<{ state: DiagnosticState }>(
      `/diagnostic/state/${visitId}`
    )
    return response.data.state
  },

  recoverLatestMessage: async (visitId: string): Promise<string | null> => {
    try {
      const state = await diagnosticService.getState(visitId)
      const msg = state?.message || state?.final_report
      return typeof msg === 'string' && msg.trim() ? msg : null
    } catch {
      return null
    }
  },

  deleteSession: async (visitId: string): Promise<void> => {
    await api.delete(`/diagnostic/delete/${visitId}`)
  },
}
