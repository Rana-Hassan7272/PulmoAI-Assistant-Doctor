"""
Script to save preprocessing components from training.

Add the following snippet at the END of your training notebook/script,
then place scaler.pkl in the bloodcount_report folder.

Training pipeline (matches feature.py):
  - Outlier capping: IQR × 3 on ALL feature columns
  - RobustScaler fitted on ALL features after SMOTE
  - Saved as scaler.pkl
"""

print("""
Add this to the end of your training code to save the scaler:

import pickle, os

output_dir = '/kaggle/working'   # adjust as needed

# Save scaler (fitted on all features after SMOTE)
with open(os.path.join(output_dir, 'scaler.pkl'), 'wb') as f:
    pickle.dump(scaler, f, protocol=pickle.HIGHEST_PROTOCOL)

# Save label encoder
with open(os.path.join(output_dir, 'label_encoder.pkl'), 'wb') as f:
    pickle.dump(le, f, protocol=pickle.HIGHEST_PROTOCOL)

# Save model
with open(os.path.join(output_dir, 'blood_disease_model.pkl'), 'wb') as f:
    pickle.dump(ensemble, f, protocol=pickle.HIGHEST_PROTOCOL)

Then copy scaler.pkl, label_encoder.pkl, and blood_disease_model.pkl
into the bloodcount_report folder.
""")

