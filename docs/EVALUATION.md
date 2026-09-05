# Evaluation

VoiceVault is **NOT EVALUATED on ASVspoof5**. No benchmark values are claimed.

Create a CSV with headers `audio_path,label`; labels are `bonafide` or `spoof`. Then run:

```powershell
cd backend
.\.venv\Scripts\python.exe tools\evaluate_antispoof.py manifest.csv --model wav2vec2
.\.venv\Scripts\python.exe tools\evaluate_antispoof.py manifest.csv --model aasist
.\.venv\Scripts\python.exe tools\evaluate_antispoof.py manifest.csv --model ensemble
```

The script reports sample count, confusion matrix, precision, recall, F1, ROC-AUC and EER when both classes exist, plus average inference latency. It stops instead of printing metrics when the selected model is unavailable.
