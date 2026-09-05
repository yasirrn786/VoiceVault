# V.O.I.C.E.

**Voice Origin, Identity & Context Engine** is a local-first, real-time Zero-Trust Voice Intrusion Prevention prototype. It continuously combines available voice, identity, signal-quality, conversation-context, requested-action, and temporal evidence into an explainable trust score and a **recommended** security decision.

It does not claim that AI voice always means fraud, that human voice means safe, or that this prototype directly blocks a bank transaction. `HOLD` and `BLOCK / ESCALATE` are policy recommendations until an external transaction system is integrated.

## What is implemented

- Purple/black V.O.I.C.E. Vault SOC dashboard based on the supplied `dashboard.html`, `threat_monitoring.html`, `workbench.html`, and `login.html` visual language.
- Browser microphone capture through the Web Audio API, mono downsampling to 16 kHz, PCM16 chunking, and native WebSocket streaming.
- FastAPI HTTP and WebSocket API with resilient per-signal failure handling.
- `faster-whisper` transcription using the cached `Systran/faster-whisper-base.en` model on CPU/int8 by default.
- Deterministic English/Hinglish-friendly context fallback for authority, urgency, secrecy, coercion, finance, OTP, PIN/CVV/password, KYC, beneficiary, amount, remote access, and bank/government impersonation signals.
- Optional Gemini context enhancement (`gemini-2.5-flash-lite`) when `GEMINI_API_KEY` is configured; rules remain the fallback.
- Stateful attack-chain correlation for `CEO_FRAUD`, `OTP_HARVESTING`, `DIGITAL_ARREST`, and `REMOTE_ACCESS_SCAM`.
- Explainable Continuous Voice Trust Fusion (CVTF), smoothing, action risk, trust bands, and policy rules.
- Manual one-click scenarios for normal speech, CEO fraud, OTP fraud, digital arrest, and remote-access fraud.
- Active random-phrase challenge with phrase verification and trust evidence updates. This is additional evidence, not proof of liveness.
- Speaker enrollment and verification through a deterministic spectral-embedding MVP adapter. The threshold is configurable and must be calibrated.
- Incident creation, local JSON metadata storage, and SHA-256 chained security-event hashes.
- Raw-audio retention off by default. Microphone chunks and temporary transcription files are discarded.
- Health, context, engine, hash-chain, API, and live WebSocket tests.

## Architecture

```text
Browser microphone / manual scenario
        │  16 kHz mono PCM16 over WebSocket
        ▼
FastAPI session manager
        ├── audio quality
        ├── faster-whisper ASR
        ├── rules + optional Gemini context
        ├── deepfake adapter (unknown when unavailable)
        ├── speaker verification adapter
        ├── liveness adapter (unknown when unavailable)
        ├── stateful attack-chain correlation
        ├── CVTF trust fusion
        ├── policy decision
        └── SHA-256 incident/event chain
                 │
                 ▼
React dashboard: transcript, risk, timeline, policy, events, health
```

The backend follows the requested modular layout under `backend/app/api`, `models`, `services`, and `schemas`. The frontend is a TypeScript React app generated with the OpenAI Sites Next-compatible `vinext` starter, Tailwind CSS, shadcn primitives, Recharts, and Lucide icons.

## Requirements

- Windows 11
- Python 3.12
- Node.js 22.13+ (tested with Node 24)
- A Chromium-family browser for microphone capture
- Internet only for first-time dependency/model download; the cached Whisper model then runs locally

## Installation

From PowerShell in the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-models.txt
cd ..\frontend
npm install
```

If `python` is not on PATH in Codex, use the Python 3.12 executable reported by the Codex workspace dependencies. This workspace already contains a working `backend/.venv`, installed npm packages, and the cached Whisper model.

Copy `.env.example` to `.env` only when changing defaults:

```powershell
Copy-Item .env.example .env
```

Important variables:

- `RAW_AUDIO_RETENTION=false`
- `WHISPER_MODEL=base.en`
- `WHISPER_DEVICE=cpu`
- `WHISPER_COMPUTE_TYPE=int8`
- `GEMINI_API_KEY=` (optional)
- `SPEAKER_SIMILARITY_THRESHOLD=0.70` (MVP default, not scientifically calibrated)
- CVTF weights, smoothing alpha, unknown-signal penalty, and high-value INR threshold are all configurable in `.env.example`.

For frontend overrides, create `frontend/.env.local` with `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL`. The defaults already point to local ports 8000 and 3000.

## Run locally

Open two PowerShell terminals from the repository root.

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Demo flow

1. Start both processes and open the dashboard.
2. Use **Normal** to confirm low context risk.
3. Run the CEO-fraud phrases in order, or press **CEO fraud** for the combined scenario.
4. Watch the trust timeline fall, context/action risk rise, events appear, `CEO_FRAUD` classify, and policy move to `HOLD TRANSACTION`.
5. Press **Challenge Caller**, repeat/type the displayed phrase, and verify the response.
6. Press **Create Incident** to view and persist the hash-chained incident report.
7. Press **Start Analysis**, approve microphone access, and speak. Two-second chunks stream to the backend and are transcribed locally.

The browser must be served from `localhost` (or HTTPS) for microphone access. If permission was previously denied, reset the site permission in the browser address bar.

## Speaker enrollment

The endpoint accepts **raw mono PCM16 at 16 kHz**, not a WAV container:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/enroll-speaker `
  -F "speaker_id=trusted-cfo" `
  -F "audio=@trusted-cfo.pcm;type=application/octet-stream"
```

Provide at least 15 seconds for a useful enrollment. Only the embedding JSON is stored under `backend/data/embeddings`; raw audio is discarded. The current adapter is a lightweight spectral baseline, not ECAPA-TDNN.

## API

- `GET /health`
- `GET /api/config`
- `POST /api/enroll-speaker`
- `POST /api/analyze-audio`
- `POST /api/analyze-context`
- `POST /api/incidents/{session_id}`
- `GET /api/incidents/{session_id}`
- `WS /ws/live-analysis`

## Testing

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
```

## Models and signal honesty

| Layer | Current implementation | Runtime behavior |
|---|---|---|
| Transcription | `Systran/faster-whisper-base.en` | Installed and cached; CPU/int8 default |
| Context | Deterministic rules | Always available |
| Context enhancement | `gemini-2.5-flash-lite` | Optional; offline/not configured falls back to rules |
| Deepfake / anti-spoof | Swappable adapter only | Returns `unknown`; no fake probability |
| Speaker identity | `spectral-embedding-mvp` | Functional experimental enrollment/matching; threshold configurable |
| Replay/liveness | Swappable adapter only | Returns `unknown`; no fabricated replay verdict |

## Privacy

`PRIVACY MODE: ON` is shown because raw-audio retention is disabled by default. PCM chunks are processed in memory. Faster-whisper receives a temporary WAV file that is deleted immediately after each transcription attempt. Incident reports contain security metadata and hashes, not microphone recordings. Embeddings are sensitive biometric-derived data and should be encrypted and access-controlled before production use.

## Known limitations

- No pretrained anti-spoof/deepfake model is configured yet, so authenticity remains `unknown`.
- No dedicated replay/liveness model is configured.
- Speaker verification is an experimental spectral baseline, not the requested SpeechBrain ECAPA-TDNN model.
- English is forced for lower latency; Hindi/Hinglish/Kannada language handling needs evaluation.
- Two-second independent chunks can split words and reduce ASR continuity.
- CVTF weights, thresholds, and policies are explainable engineering defaults, not trained or calibrated scientific parameters.
- Sessions are in process memory. Restarting the backend clears live sessions; saved incidents remain.
- Gemini behavior is not exercised without a valid API key.
- No bank, telephony/PBX, IAM, or case-management integration exists; decisions are recommendations only.
- The Web Audio `ScriptProcessorNode` works broadly but should be migrated to `AudioWorklet` for production.

## Next five highest-value improvements

1. Integrate and benchmark a verified pretrained anti-spoof model (AASIST/XLS-R compatible) on ASVspoof and in-domain call audio.
2. Replace the spectral speaker adapter with SpeechBrain ECAPA-TDNN and calibrate thresholds using target microphones, codecs, and enrolled speakers.
3. Add a dedicated replay/liveness model and a multi-turn challenge protocol evaluated against playback attacks.
4. Move streaming capture to AudioWorklet with overlapping ASR windows, voice activity detection, and multilingual Whisper routing.
5. Calibrate CVTF weights/policies on labeled SIH demo scenarios, then add persistent encrypted sessions and integrations for enforceable holds/MFA.
