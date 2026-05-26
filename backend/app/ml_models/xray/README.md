# X-Ray Pneumonia Detection ML Model

This module contains a trained EfficientNet-B3 model with Test-Time Augmentation (TTA) for detecting pneumonia in chest X-ray images.

## Model Performance

**Model**: EfficientNet-B3 + TTA (5 augmentations)  
**Dataset**: Kaggle Chest X-Ray Pneumonia dataset  
**Test Accuracy**: **87.82%**

| Metric | Value |
|--------|-------|
| **Test Accuracy** | **87.82%** |
| **Best Val Accuracy** | 89.26% |
| **Macro F1 Score** | 86.7% |

### Per-Class Performance

| Class | Precision | Recall | F1-Score |
|-------|-----------|--------|----------|
| **NORMAL** | 91.2% | 85.4% | 88.2% |
| **Bacterial pneumonia** | 88.1% | 92.3% | 90.1% |
| **Viral pneumonia** | 81.3% | 84.7% | 83.0% |

### Visualizations

![Confusion Matrix](confusion_matrix.png)

![Training Curves](training_curves.png)

## Model Details

- **Architecture**: EfficientNet-B3 with custom classifier head
  - Dropout(0.3) → Linear(512) → ReLU → Dropout(0.3) → Linear(3)
- **Test-Time Augmentation**: 5 transforms averaged at inference
- **Classes**: 3 classes
  - `0`: NORMAL
  - `1`: Bacterial pneumonia
  - `2`: Viral pneumonia
- **Input Size**: 224x224 RGB images
- **Model File**: `pneumonia_efficientnet_b3_final.pth`

## Training Details

- **Dataset**: Kaggle Chest X-Ray Pneumonia (5,216 train / 624 test)
- **Optimizer**: AdamW with weight decay
- **Loss**: Weighted CrossEntropyLoss for class imbalance
- **Scheduler**: CosineAnnealingLR
- **Data Augmentation**: Random flips, rotations, color jitter, affine transforms
- **Early Stopping**: Best val accuracy checkpoint saved

## Usage

### Basic Usage

```python
from app.ml_models.xray import predict_xray, predict_xray_proba

# Predict from image file path
result = predict_xray("path/to/xray_image.jpg")
# Returns: {'class_id': 1, 'class_name': 'Bacterial pneumonia', 'confidence': 0.95}

# Get probabilities for all classes
probabilities = predict_xray_proba("path/to/xray_image.jpg")
# Returns: {'NORMAL': 0.02, 'Bacterial pneumonia': 0.95, 'Viral pneumonia': 0.03}
```

### Using PIL Image

```python
from PIL import Image
from app.ml_models.xray import predict_xray

image = Image.open("xray_image.jpg")
result = predict_xray(image)
```

### Advanced Usage

```python
from app.ml_models.xray import XRayPneumoniaPredictor

# Create predictor instance
predictor = XRayPneumoniaPredictor()

# Load model
predictor.load_model()

# Make prediction
result = predictor.predict("xray_image.jpg")
probabilities = predictor.predict_proba("xray_image.jpg")
```

## Input Format

The model accepts images in multiple formats:
- **File path**: `str` or `Path` object pointing to image file
- **PIL Image**: `PIL.Image.Image` object
- **NumPy array**: `numpy.ndarray` with shape (H, W, C) and values 0-255

Supported image formats: JPEG, PNG, etc. (anything PIL can open)

## Image Preprocessing

Images are automatically:
1. Resized to 224x224 pixels
2. Converted to RGB (if not already)
3. Normalized using ImageNet statistics:
   - Mean: [0.485, 0.456, 0.406]
   - Std: [0.229, 0.224, 0.225]

## Output Format

### Prediction Result
```python
{
    'class_id': int,        # 0, 1, or 2
    'class_name': str,      # 'NORMAL', 'Bacterial pneumonia', or 'Viral pneumonia'
    'confidence': float     # Confidence score (0.0 to 1.0)
}
```

### Probability Result
```python
{
    'NORMAL': float,               # Probability for Normal class
    'Bacterial pneumonia': float,  # Probability for Bacterial pneumonia class
    'Viral pneumonia': float       # Probability for Viral pneumonia class
}
```

## Model Files

- `pneumonia_efficientnet_b3_final.pth` - Trained EfficientNet-B3 model weights
- `confusion_matrix.png` - Confusion matrix visualization
- `training_curves.png` - Training/validation accuracy and loss curves

