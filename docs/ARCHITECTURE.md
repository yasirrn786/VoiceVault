# VoiceVault architecture

Audio is converted to 16 kHz mono PCM and accumulated into fresh, non-overlapping analysis windows. Whisper, Wav2Vec2, AASIST and ECAPA run concurrently where applicable. AASIST uses the official 64,600-sample repeat/truncate preprocessing.

Wav2Vec2 and AASIST remain visible as independent evidence. The experimental ensemble requires consensus; disagreement produces `disagreement / verify`. Its scores are not treated as calibrated or blindly averaged into certainty. Transcript-only deterministic rules always run, while Gemini optionally adds semantic evidence and never receives audio.

CVTF combines available anti-spoof evidence, identity mismatch, context, action and signal quality. Missing evidence incurs uncertainty rather than becoming zero risk. Liveness remains unknown.

## AASIST provenance

- Source: `https://github.com/clovaai/aasist`
- Architecture: official `models/AASIST.py`
- Checkpoint: official `models/weights/AASIST.pth`
- SHA-256: `51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0`
- Configuration: AASIST, ASVspoof 2019 Logical Access, 64,600 samples
- License: MIT, Copyright NAVER Corp.
- Compatibility verification: strict state-dictionary load, 229 keys, zero missing or unexpected keys

