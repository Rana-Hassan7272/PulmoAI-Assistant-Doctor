import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { diagnosticService } from '../services/diagnostic'
import { Message, DiagnosticResponse, DiagnosticState } from '../services/types'
import { useWebSocket, WSStreamEnd, WSStreamStart } from '../services/useWebSocket'
import ChatWindow from '../components/chat/ChatWindow'
import PatientDataCard from '../components/patient/PatientDataCard'
import PatientConfirmation from '../components/patient/PatientConfirmation'
import TestResults from '../components/tests/TestResults'
import TreatmentPlan from '../components/treatment/TreatmentPlan'
import TreatmentApproval from '../components/treatment/TreatmentApproval'
import FinalReport from '../components/report/FinalReport'
import ProgressIndicator from '../components/workflow/ProgressIndicator'
import SpirometryForm, { SpirometryData } from '../components/tests/SpirometryForm'
import CBCForm, { CBCData } from '../components/tests/CBCForm'
import toast from 'react-hot-toast'

/** Convert a File to a base64 data string (without the data:... prefix). */
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // Strip the "data:image/...;base64," prefix
      resolve(result.split(',')[1] || result)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

const Diagnostic = () => {
  const { isAuthenticated, user } = useAuth()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [visitId, setVisitId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [sessionLoading, setSessionLoading] = useState(true)
  const [currentStep, setCurrentStep] = useState<string | null>(null)
  const [emergencyFlag, setEmergencyFlag] = useState(false)
  const [diagnosticState, setDiagnosticState] = useState<DiagnosticState | null>(null)
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [showTreatmentApproval, setShowTreatmentApproval] = useState(false)
  const [showSpirometryForm, setShowSpirometryForm] = useState(false)
  const [showCBCForm, setShowCBCForm] = useState(false)
  const [showReport, setShowReport] = useState(false)

  // Ref to accumulate streamed tokens into the current assistant message
  const streamBufferRef = useRef('')
  const streamingRef = useRef(false)
  const sessionStartedRef = useRef(false)

  // ---- Process a full response (shared by WS stream_end and REST fallback) ----
  const processResponse = useCallback(
    (response: { message?: string; current_step?: string | null; emergency_flag?: boolean; emergency_reason?: string | null; state?: Record<string, any> }) => {
      if (response.current_step) {
        setCurrentStep(response.current_step)
      }

      if (response.emergency_flag) {
        setEmergencyFlag(true)
        toast.error(response.emergency_reason || 'Emergency detected! Please seek immediate medical attention.')
      }

      if (response.state) {
        setDiagnosticState(response.state as DiagnosticState)

        const needsConfirmation =
          response.current_step === 'patient_intake_awaiting_confirmation' ||
          (response.state.patient_data_confirmed === false &&
            response.state.patient_name &&
            !showConfirmation)
        if (needsConfirmation) setShowConfirmation(true)

        const needsTreatmentApproval =
          (response.current_step === 'treatment_approval' ||
            response.current_step === 'rag_specialist_awaiting_approval' ||
            response.state.show_treatment_approval) &&
          response.state.treatment_plan &&
          response.state.treatment_plan.length > 0 &&
          !response.state.treatment_approved &&
          !showTreatmentApproval
        if (needsTreatmentApproval) setShowTreatmentApproval(true)

        if (response.state.show_spirometry_form_modal && !showSpirometryForm && !showCBCForm) {
          setShowSpirometryForm(true)
        } else if (response.state.show_cbc_form_modal && !showCBCForm && !showSpirometryForm) {
          setShowCBCForm(true)
        }

        const messageLower = response.message?.toLowerCase() || ''
        if (messageLower.includes('spirometry form') && !showSpirometryForm && !showCBCForm) {
          setShowSpirometryForm(true)
        } else if (messageLower.includes('cbc form') && !showCBCForm && !showSpirometryForm) {
          setShowCBCForm(true)
        }

        const isFinalStep = response.current_step === 'end' ||
          response.current_step === 'followup_agent' ||
          response.current_step === 'history_saver' ||
          response.current_step === 'report_generator'
        const hasFinalReport = response.state?.final_report ||
          (response.state?.treatment_approved &&
            response.state?.calculated_dosages &&
            (isFinalStep || response.current_step === 'dosage_calculator'))
        if (isFinalStep || hasFinalReport) {
          setShowReport(true)
          setShowConfirmation(false)
          setShowTreatmentApproval(false)
          setShowSpirometryForm(false)
          setShowCBCForm(false)
        }

        if (response.state.patient_data_confirmed) setShowConfirmation(false)

        if (response.state.show_spirometry_form_modal && !showSpirometryForm && !showCBCForm) {
          setShowSpirometryForm(true)
        } else if (response.state.show_cbc_form_modal && !showCBCForm && !showSpirometryForm) {
          setShowCBCForm(true)
        }
      }

      const isSessionComplete = response.current_step === 'end' ||
        response.current_step === 'followup_agent' ||
        response.current_step === 'history_saver' ||
        (response.state?.final_report && response.current_step !== 'treatment_approval') ||
        response.emergency_flag
      if (isSessionComplete) {
        if (response.current_step === 'followup_agent' || response.current_step === 'end' || response.state?.final_report) {
          toast.success('Diagnostic session completed. Report is ready.')
        }
        setShowConfirmation(false)
        setShowTreatmentApproval(false)
        setShowSpirometryForm(false)
        setShowCBCForm(false)
        if (response.state && (response.state.final_report || response.current_step === 'end' || response.current_step === 'followup_agent')) {
          setShowReport(true)
        }
      }
    },
    [showConfirmation, showTreatmentApproval, showSpirometryForm, showCBCForm],
  )

  // ---- WebSocket callbacks ----
  const handleWsToken = useCallback((token: string) => {
    streamBufferRef.current += token
    const accumulated = streamBufferRef.current
    setMessages((prev) => {
      const updated = [...prev]
      // Replace the last assistant (streaming) message content
      for (let i = updated.length - 1; i >= 0; i--) {
        if (updated[i].role === 'assistant' && updated[i].isThinking) {
          updated[i] = { ...updated[i], content: accumulated }
          return updated
        }
      }
      return prev
    })
  }, [])

  const handleWsStreamStart = useCallback((_data: WSStreamStart) => {
    streamBufferRef.current = ''
    streamingRef.current = true
    // Replace the "Processing..." thinking bubble with an empty streaming bubble
    setMessages((prev) => {
      const updated = prev.filter((m) => !m.isThinking)
      return [
        ...updated,
        { role: 'assistant' as const, content: '', timestamp: new Date(), isThinking: true },
      ]
    })
  }, [])

  const handleWsStreamEnd = useCallback(
    (data: WSStreamEnd) => {
      streamingRef.current = false
      // Replace the streaming bubble with the final message
      setMessages((prev) => {
        const updated = prev.filter((m) => !m.isThinking)
        return [
          ...updated,
          { role: 'assistant' as const, content: data.message, timestamp: new Date() },
        ]
      })
      if (data.visit_id) setVisitId(data.visit_id)
      processResponse(data)
      setLoading(false)
    },
    [processResponse],
  )

  const handleWsError = useCallback((msg: string) => {
    if (msg.includes('Unknown message type') || msg.includes('WebSocket is not connected')) {
      setLoading(false)
      return
    }
    toast.error(msg)
    setLoading(false)
    setMessages((prev) => prev.filter((m) => !m.isThinking))
  }, [])

  const { connect: wsConnect, disconnect: wsDisconnect, sendChat: wsSendChat, status: wsStatus } =
    useWebSocket({
      onToken: handleWsToken,
      onStreamStart: handleWsStreamStart,
      onStreamEnd: handleWsStreamEnd,
      onError: handleWsError,
    })

  useEffect(() => {
    if (isAuthenticated) {
      wsConnect()
    }
    return () => {
      wsDisconnect()
    }
  }, [isAuthenticated, wsConnect, wsDisconnect])

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login')
    }
  }, [isAuthenticated, navigate])

  // Start diagnostic session on mount (REST — always needed for initial state)
  useEffect(() => {
    if (isAuthenticated && !sessionStartedRef.current) {
      sessionStartedRef.current = true
      startSession()
    }
  }, [isAuthenticated])

  const startSession = async () => {
    setSessionLoading(true)
    try {
      const response: DiagnosticResponse = await diagnosticService.start()

      if (response.visit_id) setVisitId(response.visit_id)
      if (response.current_step) setCurrentStep(response.current_step)
      if (response.emergency_flag) {
        setEmergencyFlag(true)
        toast.error('Emergency detected! Please seek immediate medical attention.')
      }
      if (response.state) setDiagnosticState(response.state)
      if (response.message) {
        setMessages([{ role: 'assistant', content: response.message, timestamp: new Date() }])
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to start diagnostic session')
      console.error('Error starting session:', error)
    } finally {
      setSessionLoading(false)
    }
  }

  // ---- Send message: prefer WebSocket, fall back to REST ----
  const handleSend = async (message: string, file?: File) => {
    if (!visitId) {
      toast.error('Session not initialized. Please refresh the page.')
      return
    }

    // Add user message immediately
    const userMessage: Message = { role: 'user', content: message, timestamp: new Date() }
    setMessages((prev) => [...prev, userMessage])

    // Add thinking indicator
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: 'Processing...', timestamp: new Date(), isThinking: true },
    ])
    setLoading(true)

    // ---- Try WebSocket first ----
    if (wsStatus === 'connected') {
      try {
        let xrayB64: string | undefined
        if (file) {
          xrayB64 = await fileToBase64(file)
        }
        const sent = wsSendChat(message, visitId, xrayB64)
        if (sent) return // WS callbacks will handle the rest
      } catch {
        // Fall through to REST
      }
    }

    // ---- REST fallback ----
    try {
      const response: DiagnosticResponse = await diagnosticService.chat(message, visitId, file)

      // Remove thinking message
      setMessages((prev) => prev.filter((msg) => !msg.isThinking))

      // Add AI response
      if (response.message) {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: response.message, timestamp: new Date() },
        ])
      }

      if (response.visit_id) setVisitId(response.visit_id)
      processResponse(response)
    } catch (error: any) {
      setMessages((prev) => prev.filter((msg) => !msg.isThinking))

      const errorMessage = error.response?.data?.detail || error.message || 'Failed to send message. Please try again.'

      if (
        errorMessage.toLowerCase().includes('rate limit') ||
        errorMessage.toLowerCase().includes('429') ||
        errorMessage.toLowerCase().includes('quota') ||
        errorMessage.toLowerCase().includes('processing')
      ) {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: 'The system is processing your request. Please wait a moment...', timestamp: new Date(), isThinking: true },
        ])
        toast('Rate limit reached. Please wait...', { icon: '⏳' })

        setTimeout(async () => {
          try {
            setMessages((prev) => prev.filter((msg) => !msg.isThinking))
            const retryResponse = await diagnosticService.chat(message, visitId, file)
            if (retryResponse.current_step) setCurrentStep(retryResponse.current_step)
            if (retryResponse.state) setDiagnosticState(retryResponse.state)
            if (retryResponse.message) {
              setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: retryResponse.message, timestamp: new Date() },
              ])
            }
          } catch {
            setMessages((prev) => prev.filter((msg) => !msg.isThinking))
            toast.error('Still processing. Please try again in a moment.')
          } finally {
            setLoading(false)
          }
        }, 3000)
        return
      }

      toast.error(errorMessage)
      console.error('Error sending message:', error)
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setLoading(false)
    }
  }

  if (sessionLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Starting diagnostic session...</p>
        </div>
      </div>
    )
  }

  const handleConfirm = async () => {
    setShowConfirmation(false)
    handleSend('Yes, that is correct')
  }

  const handleReject = async (corrections: string) => {
    setShowConfirmation(false)
    handleSend(corrections || 'No, that is not correct.')
  }

  const handleTreatmentApprove = async () => {
    setShowTreatmentApproval(false)
    handleSend('approve')
  }

  const handleTreatmentReject = async (modifications: string) => {
    setShowTreatmentApproval(false)
    handleSend(modifications || 'I would like to modify the treatment plan.')
  }

  const handleTreatmentQuestion = async (question: string) => {
    handleSend(question)
  }

  const handleSpirometrySubmit = async (data: SpirometryData) => {
    setShowSpirometryForm(false)
    const ratio = data.fvc > 0 ? ((data.fev1 / data.fvc) * 100).toFixed(2) : data.fev1_fvc.toFixed(2)
    const message = `Spirometry test results submitted: FEV1=${data.fev1}L, FVC=${data.fvc}L, FEV1/FVC=${ratio}%`
    handleSend(message)
  }

  const handleCBCSubmit = async (data: CBCData) => {
    setShowCBCForm(false)
    const fieldMapping: Record<string, string> = {
      wbc: 'WBC', rbc: 'RBC', hemoglobin: 'HGB', hematocrit: 'HCT',
      platelets: 'PLT', mcv: 'MCV', mch: 'MCH', mchc: 'MCHC',
    }
    const values = Object.entries(data)
      .filter(([_, value]) => value !== undefined)
      .map(([key, value]) => `${fieldMapping[key] || key}=${value}`)
      .join(', ')
    handleSend(`CBC test results submitted: ${values}`)
  }

  // Show final report if session is complete
  if (showReport && diagnosticState) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <FinalReport state={diagnosticState} />
        <div className="mt-6 text-center">
          <button
            onClick={() => navigate('/dashboard')}
            className="btn-primary"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Patient Data Card */}
      {diagnosticState && !showConfirmation && (
        <PatientDataCard state={diagnosticState} />
      )}

      {/* Test Results */}
      {diagnosticState && (
        <TestResults state={diagnosticState} />
      )}

      {/* Treatment Plan */}
      {diagnosticState && diagnosticState.treatment_plan && !showTreatmentApproval && (
        <TreatmentPlan state={diagnosticState} />
      )}

      {/* Confirmation Modal */}
      {showConfirmation && diagnosticState && (
        <PatientConfirmation
          state={diagnosticState}
          onConfirm={handleConfirm}
          onReject={handleReject}
          onClose={() => setShowConfirmation(false)}
        />
      )}

      {/* Treatment Approval Modal */}
      {showTreatmentApproval && diagnosticState && (
        <TreatmentApproval
          state={diagnosticState}
          onApprove={handleTreatmentApprove}
          onReject={handleTreatmentReject}
          onQuestion={handleTreatmentQuestion}
          onClose={() => setShowTreatmentApproval(false)}
        />
      )}

      {/* Spirometry Form Modal */}
      {showSpirometryForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900">Spirometry Test Results</h2>
              <button
                onClick={() => setShowSpirometryForm(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <SpirometryForm
              onSubmit={handleSpirometrySubmit}
              onCancel={() => setShowSpirometryForm(false)}
            />
          </div>
        </div>
      )}

      {/* CBC Form Modal */}
      {showCBCForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900">CBC Blood Test Results</h2>
              <button
                onClick={() => setShowCBCForm(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <CBCForm
              onSubmit={handleCBCSubmit}
              onCancel={() => setShowCBCForm(false)}
            />
          </div>
        </div>
      )}

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Diagnostic Session</h1>
            <p className="text-gray-600 mt-1">
              {user?.email} • Patient ID: {user?.patient_id || 'N/A'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* WebSocket Status Indicator */}
            <div className="flex items-center gap-1.5" title={`Connection: ${wsStatus}`}>
              <div className={`w-2 h-2 rounded-full ${
                wsStatus === 'connected' ? 'bg-green-500' :
                wsStatus === 'connecting' || wsStatus === 'authenticating' ? 'bg-yellow-500 animate-pulse' :
                wsStatus === 'reconnecting' ? 'bg-orange-500 animate-pulse' :
                'bg-gray-400'
              }`} />
              <span className="text-xs text-gray-500">
                {wsStatus === 'connected' ? 'Live' :
                 wsStatus === 'connecting' || wsStatus === 'authenticating' ? 'Connecting...' :
                 wsStatus === 'reconnecting' ? 'Reconnecting...' : 'REST'}
              </span>
            </div>
            {visitId && (
              <div className="text-sm text-gray-500">
                Visit ID: <span className="font-mono">{visitId.slice(0, 8)}...</span>
              </div>
            )}
          </div>
        </div>

        {/* Progress Indicator */}
        {currentStep && (
          <div className="mt-4">
            <ProgressIndicator currentStep={currentStep} />
          </div>
        )}

        {/* Emergency Alert */}
        {emergencyFlag && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center">
              <svg
                className="w-5 h-5 text-red-600 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              <p className="text-red-800 font-medium">
                Emergency Alert: Please seek immediate medical attention!
              </p>
            </div>
          </div>
        )}
      </div>


      {/* Chat Window */}
      <div className="card p-0 h-[600px] flex flex-col">
        <ChatWindow
          messages={messages}
          onSend={handleSend}
          loading={loading}
          disabled={emergencyFlag}
        />
      </div>

      {/* Session Info */}
      <div className="mt-4 text-center text-sm text-gray-500">
        <p>
          Your conversation is being saved. You can close this page and return later using the
          same session.
        </p>
      </div>
    </div>
  )
}

export default Diagnostic

