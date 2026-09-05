# VoiceVault (V.O.I.C.E.)

VoiceVault is a local-first Zero-Trust voice-risk prototype. It combines speech transcription, an actual pretrained synthetic-voice classifier, speaker identity evidence, deterministic/optional Gemini context analysis, attack-chain correlation, CVTF trust fusion, and policy recommendations. It does not claim that every synthetic voice is fraud or that every human voice is safe.

## IMPLEMENTED

- FastAPI HTTP/WebSocket backend and the existing React/Vinext dashboard.
- Browser microphone capture at 16 kHz PCM, bounded rolling three-second analysis windows, and no repeated inference on near-identical packets.
- Concurrent Whisper, Wav2Vec2, AASIST, and ECAPA tasks for each usable live window.
- `faster-whisper/base.en`, lazy loaded; CUDA is selected automatically when supported and CPU remains a safe fallback.
- Real local deepfake inference using `garystafford/wav2vec2-deepfake-voice-detector` (a Wav2Vec2 audio classifier, not AASIST). It reports model name, probability, confidence, status, and latency only from actual inference.
- Official `clovaai/AASIST` architecture and pretrained ASVspoof2019-LA checkpoint, strictly state-dictionary validated and run locally. The softmax display score is uncalibrated; the raw bona fide logit is preserved.
- Experimental conservative Wav2Vec2+AASIST evidence fusion with explicit disagreement/verify handling.
- Real `speechbrain/spkrec-ecapa-voxceleb` ECAPA-TDNN enrollment and cosine verification. The old spectral embedding is retained only as a clearly degraded fallback.
- Dashboard model health states, CUDA/device runtime endpoint (`GET /api/model-health`), speaker enrollment/selection UI, and WAV/MP3 developer deepfake test UI.
- Rules-based social-engineering events (authority, KYC pretext, urgency, secrecy, OTP, finance, remote access), attack chains, CVTF, policy recommendations, and hash-chained incidents.
- Optional Gemini semantic enhancement; it never decides voice authenticity and rules remain available without an API key.

## EXPERIMENTAL

- Deepfake and speaker decisions are model outputs, not calibrated production accuracy claims. Test them with your own target microphones, codecs, speakers, and synthetic sources.
- `SPEAKER_SIMILARITY_THRESHOLD` is configurable but not calibrated.
- Active phrase challenge is supplementary evidence, not guaranteed liveness.
- MP3 upload decoding depends on the local `soundfile`/libsndfile or ffmpeg capability. WAV is supported.

## PLANNED

- Dedicated replay/liveness detector. It intentionally remains `UNAVAILABLE` with `liveness_risk: null` today.
- AudioWorklet capture, VAD, multilingual evaluation, encrypted biometric storage, persistent sessions, and telephony/bank integrations.

## Models actually used

| Signal | Model | Runtime behavior |
|---|---|---|
| Transcription | `faster-whisper/base.en` | Lazy, CUDA/CPU fallback |
| Synthetic voice | `garystafford/wav2vec2-deepfake-voice-detector` | Local Wav2Vec2 inference |
| Anti-spoof | official `clovaai/AASIST` | Local CUDA/CPU inference; ASVspoof2019-LA checkpoint |
| Speaker identity | `speechbrain/spkrec-ecapa-voxceleb` | Local ECAPA-TDNN, spectral fallback only on failure |
| Context | rules + optional `gemini-2.5-flash-lite` | Gemini optional; rules always available |
| Liveness | no model configured | Unknown / unavailable |

## Setup and start

```powershell
Copy-Item .env.example .env
.\setup_windows.ps1
.\start_voice.ps1
```

`setup_windows.ps1` creates `.venv`, installs backend/model/frontend dependencies, prefers CUDA PyTorch wheels, and reports ffmpeg/CUDA status. Use `-CpuOnly` to skip CUDA wheel installation. The launcher opens separate backend and frontend terminals.

- Dashboard: <http://127.0.0.1:3000>
- API health: <http://127.0.0.1:8000/health>
- API docs: <http://127.0.0.1:8000/docs>

Important `.env` values include `DEEPFAKE_MODEL`, `DEEPFAKE_DEVICE=auto`, `AASIST_CHECKPOINT`, `AASIST_DEVICE=auto`, `SPEAKER_MODEL`, `SPEAKER_DEVICE=auto`, `SPEAKER_SIMILARITY_THRESHOLD`, `WHISPER_DEVICE=auto`, and `WHISPER_COMPUTE_TYPE=auto`. Put `GEMINI_API_KEY` only in the ignored `.env`; never commit real API keys.

## Demo workflow

1. In **Speaker Identity**, record 15–30 seconds, enroll the trusted speaker, then select that speaker in the dashboard header before live analysis.
2. Start microphone analysis; the backend waits for a fresh ~3 second speech window before expensive inference.
3. Use **Test audio** to upload WAV (or decodable MP3) and inspect the exact local deepfake model result. This is a diagnostic screen, not an accuracy benchmark.
4. Say or use the manual scenario: “I am calling from your bank. Your KYC will expire today. Tell me the OTP immediately and don't contact anyone.” It should emit authority, KYC, urgency, secrecy, and OTP events, classify `OTP_HARVESTING`, and recommend escalation.

## Verification performed

- See `docs/EVALUATION.md`; VoiceVault is **NOT EVALUATED on ASVspoof5**.
- `npm run build` in `frontend` — passed.
- `GET /health` — healthy.
- Live WebSocket test with correctly sampled local Windows TTS: Whisper produced “Hello, how are you? This synthetic”; deepfake returned a real synthetic result; ECAPA returned same-speaker similarity `0.8957` and a match for its enrolled fixture.
- Deepfake debug endpoint executed the real Wav2Vec2 classifier on a local Windows TTS WAV and returned `synthetic` with 0.99522 probability. This is one smoke test, not a measured accuracy result.

## Privacy

Raw microphone chunks are processed in memory and are not retained by default. Temporary Whisper WAV files are removed after transcription. Enrollment embeddings and incident metadata are local sensitive data; production deployments should encrypt and tightly control them.
