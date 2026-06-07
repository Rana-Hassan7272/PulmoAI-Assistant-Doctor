import { useState, useEffect } from 'react'

interface SpirometryFormProps {
  onSubmit: (data: SpirometryData) => void
  onCancel?: () => void
}

export interface SpirometryData {
  fev1: number
  fvc: number
  fev1_fvc: number
}

const SpirometryForm: React.FC<SpirometryFormProps> = ({ onSubmit, onCancel }) => {
  const [fev1, setFev1] = useState('')
  const [fvc, setFvc] = useState('')
  const [fev1Fvc, setFev1Fvc] = useState('')

  useEffect(() => {
    const fev1Val = parseFloat(fev1)
    const fvcVal = parseFloat(fvc)
    if (!isNaN(fev1Val) && !isNaN(fvcVal) && fvcVal > 0) {
      const ratio = (fev1Val / fvcVal) * 100
      setFev1Fvc(ratio.toFixed(2))
    } else {
      setFev1Fvc('')
    }
  }, [fev1, fvc])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const fev1Val = parseFloat(fev1)
    const fvcVal = parseFloat(fvc)
    if (isNaN(fev1Val) || isNaN(fvcVal) || fvcVal <= 0) {
      return
    }
    const ratio = (fev1Val / fvcVal) * 100

    onSubmit({
      fev1: fev1Val,
      fvc: fvcVal,
      fev1_fvc: Math.round(ratio * 100) / 100,
    })
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            FEV1 (Liters)
          </label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={fev1}
            onChange={(e) => setFev1(e.target.value)}
            className="input-field"
            placeholder="e.g., 2.5"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            FVC (Liters)
          </label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={fvc}
            onChange={(e) => setFvc(e.target.value)}
            className="input-field"
            placeholder="e.g., 4.2"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            FEV1/FVC Ratio (%)
          </label>
          <input
            type="number"
            step="0.01"
            value={fev1Fvc}
            readOnly
            className="input-field bg-gray-50"
            placeholder="Auto-calculated"
            required
          />
          <p className="text-xs text-gray-500 mt-1">
            Calculated as (FEV1 ÷ FVC) × 100 — e.g. 2.5 ÷ 4.2 = 59.52%
          </p>
        </div>
        <div className="flex space-x-3">
          <button type="submit" className="btn-primary flex-1">
            Submit Results
          </button>
          {onCancel && (
            <button type="button" onClick={onCancel} className="btn-secondary flex-1">
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  )
}

export default SpirometryForm
