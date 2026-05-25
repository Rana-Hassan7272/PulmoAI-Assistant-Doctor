import { DiagnosticState } from '../../services/types'

interface TreatmentPlanProps {
  state: DiagnosticState
}

const TreatmentPlan: React.FC<TreatmentPlanProps> = ({ state }) => {
  if (!state.diagnosis && !state.treatment_plan) {
    return null
  }

  return (
    <div className="card border-l-4 border-l-medical-500 mb-4">
      <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center">
        <svg
          className="w-6 h-6 mr-2 text-medical-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
          />
        </svg>
        Diagnosis & Treatment Plan
      </h2>

      {state.diagnosis && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Diagnosis</h3>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-gray-800">
              {typeof state.diagnosis === 'string'
                ? state.diagnosis
                : typeof state.diagnosis === 'object' && state.diagnosis !== null
                  ? (state.diagnosis as any).primary || (state.diagnosis as any).primary_diagnosis || JSON.stringify(state.diagnosis)
                  : String(state.diagnosis)}
            </p>
          </div>
        </div>
      )}

      {state.treatment_plan && state.treatment_plan.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Treatment Plan</h3>
          <div className="space-y-3">
            {state.treatment_plan.map((treatment, index) => (
              <div
                key={index}
                className="bg-gray-50 border border-gray-200 rounded-lg p-4 flex items-start"
              >
                <span className="flex-shrink-0 w-6 h-6 bg-medical-600 text-white rounded-full flex items-center justify-center text-sm font-medium mr-3">
                  {index + 1}
                </span>
                <p className="text-gray-800 flex-1">
                  {typeof treatment === 'string' 
                    ? treatment 
                    : JSON.stringify(treatment)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {state.calculated_dosages && Object.keys(state.calculated_dosages).length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Calculated Dosages</h3>
          <div className="space-y-3">
            {Object.entries(state.calculated_dosages).map(([medication, dosage]: [string, any]) => (
              <div
                key={medication}
                className="bg-yellow-50 border border-yellow-200 rounded-lg p-4"
              >
                <h4 className="font-semibold text-gray-900 mb-2">{medication}</h4>
                <div className="grid md:grid-cols-2 gap-2 text-sm">
                  {dosage.dose && (
                    <div>
                      <span className="text-gray-600">Dose:</span>
                      <span className="ml-2 font-medium">{dosage.dose}</span>
                    </div>
                  )}
                  {dosage.frequency && (
                    <div>
                      <span className="text-gray-600">Frequency:</span>
                      <span className="ml-2 font-medium">{dosage.frequency}</span>
                    </div>
                  )}
                  {dosage.duration && (
                    <div>
                      <span className="text-gray-600">Duration:</span>
                      <span className="ml-2 font-medium">{dosage.duration}</span>
                    </div>
                  )}
                  {dosage.notes && (
                    <div className="md:col-span-2">
                      <span className="text-gray-600">Notes:</span>
                      <span className="ml-2">{dosage.notes}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {state.home_remedies && state.home_remedies.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Home Remedies</h3>
          <ul className="list-disc list-inside space-y-2 text-gray-800">
            {state.home_remedies.map((remedy: string | any, index: number) => (
              <li key={index}>
                {typeof remedy === 'string' 
                  ? remedy 
                  : JSON.stringify(remedy)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {state.followup_instruction && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Follow-up Instructions</h3>
          {Array.isArray(state.followup_instruction) ? (
            <ul className="list-disc list-inside space-y-1 text-gray-800">
              {state.followup_instruction.map((item: string, i: number) => (
                <li key={i}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-800">
              {typeof state.followup_instruction === 'string'
                ? state.followup_instruction
                : JSON.stringify(state.followup_instruction)}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default TreatmentPlan

