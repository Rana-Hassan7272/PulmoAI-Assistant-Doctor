# Blood Count Report Disease Prediction System

This module provides functionality for predicting blood-related diseases from blood count values:
1. **Manual Input** - Accepts blood count values via API
2. **Disease Prediction** - Predicts blood-related diseases using trained ensemble model

## Model Performance

**Model**: Voting Ensemble (Random Forest + XGBoost + Gradient Boosting)  
**Dataset**: Anemia Types Classification (Kaggle) - 4,680 samples  
**Test Accuracy**: **99.83%**

| Metric | Value |
|--------|-------|
| **Test Accuracy** | **99.83%** |
| **Macro Avg Precision** | 99.84% |
| **Macro Avg Recall** | 99.83% |
| **Macro Avg F1** | 99.83% |

### Per-Class Performance (9 Classes)

| Class | Precision | Recall | F1-Score | Support |
|-------|-----------|--------|----------|---------|
| **Healthy** | 98.53% | 100.00% | 99.26% | 67 |
| **Iron deficiency anemia** | 100.00% | 100.00% | 100.00% | 67 |
| **Leukemia** | 100.00% | 100.00% | 100.00% | 67 |
| **Leukemia with thrombocytopenia** | 100.00% | 100.00% | 100.00% | 68 |
| **Macrocytic anemia** | 100.00% | 100.00% | 100.00% | 67 |
| **Normocytic hypochromic anemia** | 100.00% | 98.51% | 99.25% | 67 |
| **Normocytic normochromic anemia** | 100.00% | 100.00% | 100.00% | 68 |
| **Other microcytic anemia** | 100.00% | 100.00% | 100.00% | 67 |
| **Thrombocytopenia** | 100.00% | 100.00% | 100.00% | 67 |

### Visualizations

**Confusion Matrix:**

![Confusion Matrix](confusion_matrix.png)

**Feature Importance:**

![Feature Importance](feature_importance.png)

**Per-Class Accuracy:**

![Per-Class Accuracy](per_class_accuracy.png)

## System Overview

The system works in three stages:

```
Lab Report Image → OCR → Text → Parser → Structured Data → ML Model → Prediction
```

### 1. OCR Extraction (`ocr_extractor.py`)

Extracts text from lab report images using Tesseract OCR with multiple preprocessing methods for better accuracy.

**Features:**
- Multiple image preprocessing methods (grayscale, threshold, denoise, enhance)
- Multiple OCR attempts with different PSM (Page Segmentation Mode) settings
- Automatic selection of best extraction result
- Handles various image formats (JPEG, PNG, etc.)

**Usage:**
```python
from app.ml_models.bloodcount_report import extract_text_from_image
from PIL import Image

image = Image.open("lab_report.jpg")
text = extract_text_from_image(image)
print(text)
```

**Advanced Usage:**
```python
from app.ml_models.bloodcount_report import OCRExtractor

extractor = OCRExtractor()
# Get all extraction attempts
all_results = extractor.extract_with_multiple_attempts(image)
# Get best result
best_text = extractor.get_best_extraction(image)
```

### 2. Text Parsing (`text_parser.py`)

Parses OCR-extracted text to extract structured blood count values using regex patterns.

**Features:**
- Handles various lab report formats and naming conventions
- Validates extracted values against expected ranges
- Returns structured dictionary with all 14 required parameters
- Provides validation status (missing parameters, extraction count)

**Usage:**
```python
from app.ml_models.bloodcount_report import parse_lab_report_text

ocr_text = "WBC: 7.5, HGB: 14.0, RBC: 4.5..."
parsed = parse_lab_report_text(ocr_text)
print(parsed)  # {'WBC': 7.5, 'HGB': 14.0, ...}
```

**Advanced Usage:**
```python
from app.ml_models.bloodcount_report import LabReportParser

parser = LabReportParser()
result = parser.parse_and_validate(ocr_text)

print(result['values'])  # Extracted values
print(result['validation'])  # Validation status
```

### 3. Disease Prediction (`feature.py`)

Predicts blood-related diseases from structured blood count data using trained ensemble model.

**Model Details:**
- **Architecture**: VotingClassifier Ensemble (Soft Voting)
  - Random Forest (300 estimators, max_depth=None)
  - XGBoost (300 estimators, max_depth=6, lr=0.05)
  - Gradient Boosting (200 estimators, max_depth=5, lr=0.05)
- **Preprocessing**: RobustScaler, IQR outlier capping, SMOTE balancing
- **Training**: 5-Fold Stratified Cross-Validation
- **Classes**: 9 disease classes
  - `0`: Normocytic hypochromic anemia
  - `1`: Iron deficiency anemia
  - `2`: Other microcytic anemia
  - `3`: Leukemia
  - `4`: Healthy
  - `5`: Thrombocytopenia
  - `6`: Normocytic normochromic anemia
  - `7`: Leukemia with thrombocytopenia
  - `8`: Macrocytic anemia

**Usage:**
```python
from app.ml_models.bloodcount_report import predict_blood_disease

blood_data = {
    'WBC': 7.5, 'LYMp': 35.0, 'NEUTp': 60.0, 'LYMn': 2.6, 'NEUTn': 4.5,
    'RBC': 4.5, 'HGB': 14.0, 'HCT': 42.0, 'MCV': 90.0, 'MCH': 30.0,
    'MCHC': 33.0, 'PLT': 250.0, 'PDW': 12.0, 'PCT': 0.25
}

result = predict_blood_disease(blood_data)
# Returns: {'class_id': 4, 'disease_name': 'Healthy'}
```

## Complete Workflow Example

```python
from PIL import Image
from app.ml_models.bloodcount_report import (
    extract_text_from_image,
    parse_lab_report_text,
    predict_blood_disease
)

# Step 1: OCR
image = Image.open("lab_report.jpg")
ocr_text = extract_text_from_image(image)

# Step 2: Parse
parsed_values = parse_lab_report_text(ocr_text)

# Step 3: Predict (only if all values extracted)
if all(v is not None for v in parsed_values.values()):
    prediction = predict_blood_disease(parsed_values)
    print(f"Predicted Disease: {prediction['disease_name']}")
else:
    print("Missing some values, cannot make prediction")
```

## FastAPI Integration

The system is integrated into FastAPI with a single endpoint:

### Endpoint: `POST /labs/analyze-report`

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: Image file (lab report image)

**Response:**
```json
{
    "ocr_result": {
        "text": "extracted text...",
        "success": true,
        "message": "Text extracted successfully"
    },
    "parsed_values": {
        "WBC": 7.5,
        "HGB": 14.0,
        ...
    },
    "validation": {
        "is_valid": true,
        "missing_params": [],
        "extracted_count": 14,
        "total_count": 14
    },
    "prediction": {
        "class_id": 4,
        "disease_name": "Healthy"
    },
    "probabilities": {
        "probabilities": {
            "Healthy": 0.95,
            "Leukemia": 0.02,
            ...
        }
    },
    "error": null
}
```

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/labs/analyze-report" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@lab_report.jpg"
```

**Example using Python requests:**
```python
import requests

url = "http://localhost:8000/labs/analyze-report"
with open("lab_report.jpg", "rb") as f:
    response = requests.post(url, files={"file": f})
    result = response.json()
    print(result)
```

## Required Blood Count Parameters

All 14 parameters must be extracted for prediction:

- **WBC**: White Blood Cell count
- **LYMp**: Lymphocyte percentage
- **NEUTp**: Neutrophil percentage
- **LYMn**: Lymphocyte absolute count
- **NEUTn**: Neutrophil absolute count
- **RBC**: Red Blood Cell count
- **HGB**: Hemoglobin (g/dL)
- **HCT**: Hematocrit (%)
- **MCV**: Mean Corpuscular Volume (fL)
- **MCH**: Mean Corpuscular Hemoglobin (pg)
- **MCHC**: Mean Corpuscular Hemoglobin Concentration (g/dL)
- **PLT**: Platelet count (×10³/µL)
- **PDW**: Platelet Distribution Width
- **PCT**: Plateletcrit

## Error Handling

The system handles various error scenarios:

1. **Invalid Image Format**: Returns 400 error
2. **OCR Failure**: Continues with partial text, reports in response
3. **Missing Parameters**: Returns validation status with missing parameters list
4. **Invalid Values**: Validates ranges, warns about out-of-range values
5. **Prediction Failure**: Returns error message in response

## Dependencies

- `pytesseract` - OCR engine
- `opencv-python` - Image preprocessing
- `Pillow` - Image handling
- `pandas`, `numpy` - Data processing
- `scikit-learn` - ML models (Random Forest, Gradient Boosting)
- `xgboost` - XGBoost classifier
- `imbalanced-learn` - SMOTE for class balancing

## Installation Notes

### Tesseract OCR Installation

**Windows:**
1. Download Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install and add to PATH
3. Or uncomment and set path in `ocr_extractor.py`:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

## Model Files

- `blood_disease_model.pkl` - Trained ensemble model (RF + XGBoost + Gradient Boosting)
- `scaler.pkl` - RobustScaler for feature normalization
- `label_encoder.pkl` - LabelEncoder for disease labels
- `confusion_matrix.png` - Confusion matrix visualization
- `feature_importance.png` - Feature importance plot
- `per_class_accuracy.png` - Per-class accuracy bar chart

## Testing

See testing instructions in the main project README or run:

```python
# Test OCR
from app.ml_models.bloodcount_report import extract_text_from_image
from PIL import Image
image = Image.open("test_lab_report.jpg")
text = extract_text_from_image(image)
print(text)

# Test Parser
from app.ml_models.bloodcount_report import parse_lab_report_text
parsed = parse_lab_report_text(text)
print(parsed)

# Test Prediction
from app.ml_models.bloodcount_report import predict_blood_disease
if all(v is not None for v in parsed.values()):
    result = predict_blood_disease(parsed)
    print(result)
```

## What Was Implemented

### Step 1: OCR Extractor (`ocr_extractor.py`)
- ✅ Tesseract OCR integration
- ✅ Multiple image preprocessing methods (grayscale, threshold, denoise, enhance)
- ✅ Multiple OCR attempts with different PSM modes
- ✅ Automatic best result selection

### Step 2: Text Parser (`text_parser.py`)
- ✅ Regex patterns for all 14 blood count parameters
- ✅ Handles various naming conventions and formats
- ✅ Value validation against expected ranges
- ✅ Validation status reporting

### Step 3: FastAPI Route (`fastapi_routers/lab_results.py`)
- ✅ New endpoint: `POST /labs/analyze-report`
- ✅ Complete workflow: Upload → OCR → Parse → Predict
- ✅ Comprehensive error handling
- ✅ Structured response with all stages

### Step 4: Schemas (`schemas/lab_results.py`)
- ✅ `OCRResult` - OCR extraction results
- ✅ `ParsedValues` - Extracted blood count values
- ✅ `ValidationStatus` - Validation information
- ✅ `PredictionResult` - Disease prediction
- ✅ `PredictionProbabilities` - All class probabilities
- ✅ `LabReportAnalysisResponse` - Complete analysis response

### Step 5: Dependencies (`requirements.txt`)
- ✅ Added `pytesseract` for OCR
- ✅ Added `pdf2image` for PDF support (optional)

### Step 6: Error Handling
- ✅ Image validation
- ✅ OCR failure handling
- ✅ Parsing validation
- ✅ Prediction error handling
- ✅ User-friendly error messages

### Step 7: Image Preprocessing & Multiple OCR Attempts
- ✅ 5 preprocessing methods (default, grayscale, threshold, denoise, enhance)
- ✅ 3 PSM modes (psm6, psm11, psm12)
- ✅ Automatic best result selection (longest text)
- ✅ All attempts logged for debugging

### Step 8: Testing Instructions
- ✅ Provided in this README
- ✅ Example code snippets
- ✅ API usage examples

## File Structure

```
backend/app/ml_models/bloodcount_report/
├── __init__.py                 # Module exports
├── feature.py                  # ML model predictor
├── ocr_extractor.py            # OCR functionality
├── text_parser.py              # Text parsing
├── README.md                   # This file
├── blood_disease_model.pkl     # Trained ensemble model
├── scaler.pkl                  # RobustScaler
├── label_encoder.pkl           # Label encoder
├── confusion_matrix.png        # Confusion matrix viz
├── feature_importance.png      # Feature importance plot
└── per_class_accuracy.png      # Per-class accuracy chart
```
