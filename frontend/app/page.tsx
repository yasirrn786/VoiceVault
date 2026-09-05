'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, AudioLines, Bell, CircleStop, FileWarning, Fingerprint, Gauge,
  Headphones, History, LockKeyhole, Mic, Play, Radar, RefreshCw, ShieldAlert,
  ShieldCheck, Siren, TerminalSquare, UserRoundCheck,
} from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { startPcmStream, type AudioStreamHandle } from '@/lib/audio-stream';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/live-analysis';
const suspicious = /(otp|pin|cvv|upi|password|bank transfer|beneficiary|kyc|screen share|remote access|urgent(?:ly)?|immediately|confidential|don['’]?t tell anyone|do not contact|police|cbi|digital arrest)/gi;

const scenarios = [
  ['Normal', 'Hello, are we still meeting for lunch tomorrow?'],
  ['CEO fraud', 'I am the CFO. Transfer ₹8 lakh to this new beneficiary immediately. This is confidential, do not contact finance.'],
  ['OTP scam', 'I am calling from your bank. Your KYC will expire today. Tell me the OTP.'],
  ['Digital arrest', 'This is CBI. You are under investigation. Do not contact anybody. Transfer the verification amount now.'],
  ['Remote access', 'Install this app and share your screen so I can fix your bank account.'],
] as const;

type SecurityEvent = { event: string; timestamp: number; severity: string; confidence: number; source: string; event_hash?: string };
type Transcript = { timestamp: number; text: string; confidence: number };
type AnalysisUpdate = {
  type: 'analysis_update'; session_id: string; timestamp: number; transcript: { text: string; confidence: number };
  context: { context_risk: number; action_risk: number; claimed_identity?: string; amount?: number; currency?: string };
  signals: { synthetic_voice_risk: { synthetic_score: number | null; label: string }; speaker: { speaker_similarity: number | null; speaker_match: boolean | 'unknown' }; liveness: { liveness_risk: number | null; label: string }; audio_quality: { score: number; status: string } | null };
  trust_score: number; risk_score: number; trust_band: string; policy_decision: string; policy_reasons: string[]; attack_chain?: string; events: SecurityEvent[]; model_health: Record<string, string>;
};

const initialHealth = { Whisper: 'STANDBY', Deepfake: 'UNAVAILABLE', Speaker: 'DEGRADED', Liveness: 'UNAVAILABLE', Gemini: 'NOT_CONFIGURED' };

export default function Home() {
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [trust, setTrust] = useState(88);
  const [band, setBand] = useState('TRUSTED');
  const [policy, setPolicy] = useState('ALLOW');
  const [policyReasons, setPolicyReasons] = useState(['No material threat condition met']);
  const [attack, setAttack] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<Transcript[]>([]);
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [timeline, setTimeline] = useState([{ time: 0, trust: 88 }]);
  const [health, setHealth] = useState<Record<string, string>>(initialHealth);
  const [signals, setSignals] = useState({ synthetic: null as number | null, speaker: null as number | null, liveness: null as number | null, context: 0, action: 0, quality: 1 });
  const [error, setError] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<string | null>(null);
  const [challengeInput, setChallengeInput] = useState('');
  const [incident, setIncident] = useState<Record<string, unknown> | null>(null);
  const [selectedSpeaker, setSelectedSpeaker] = useState('');
  const [speakers, setSpeakers] = useState<string[]>([]);
  const [speakerDialog, setSpeakerDialog] = useState(false);
  const [debugDialog, setDebugDialog] = useState(false);
  const [speakerIdInput, setSpeakerIdInput] = useState('');
  const [enrollmentSeconds, setEnrollmentSeconds] = useState(0);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollmentResult, setEnrollmentResult] = useState<string | null>(null);
  const [debugFile, setDebugFile] = useState<File | null>(null);
  const [debugResult, setDebugResult] = useState<Record<string, unknown> | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<AudioStreamHandle | null>(null);
  const enrollmentAudioRef = useRef<AudioStreamHandle | null>(null);
  const enrollmentChunksRef = useRef<ArrayBuffer[]>([]);

  const loadSpeakers = useCallback(async () => {
    try { const response = await fetch(`${API_URL}/api/speakers`); if (response.ok) setSpeakers((await response.json()).speakers || []); }
    catch { /* Backend may not be running yet. */ }
  }, []);

  useEffect(() => { void loadSpeakers(); }, [loadSpeakers]);

  const startEnrollment = useCallback(async () => {
    setError(null); setEnrollmentResult(null); setEnrollmentSeconds(0); enrollmentChunksRef.current = [];
    try {
      enrollmentAudioRef.current = await startPcmStream((chunk) => { enrollmentChunksRef.current.push(chunk.slice(0)); setEnrollmentSeconds((seconds) => seconds + 2); });
      setEnrolling(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Microphone start failed.'); }
  }, []);

  const finishEnrollment = useCallback(async () => {
    await enrollmentAudioRef.current?.stop(); enrollmentAudioRef.current = null; setEnrolling(false);
    if (!speakerIdInput.trim()) { setError('Enter a trusted speaker name or ID first.'); return; }
    if (enrollmentSeconds < 14) { setError('Record at least 15 seconds for a usable speaker enrollment.'); return; }
    const total = enrollmentChunksRef.current.reduce((size, item) => size + item.byteLength, 0);
    const joined = new Uint8Array(total); let offset = 0;
    enrollmentChunksRef.current.forEach((item) => { joined.set(new Uint8Array(item), offset); offset += item.byteLength; });
    try {
      const form = new FormData(); form.append('speaker_id', speakerIdInput.trim()); form.append('audio', new Blob([joined], { type: 'application/octet-stream' }), 'enrollment.pcm');
      const response = await fetch(`${API_URL}/api/enroll-speaker`, { method: 'POST', body: form });
      const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'Enrollment failed.');
      setEnrollmentResult(`Stored with ${result.model}. Select this identity for later live analysis.`); setSelectedSpeaker(speakerIdInput.trim()); await loadSpeakers();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Enrollment failed.'); }
  }, [enrollmentSeconds, loadSpeakers, speakerIdInput]);

  const runDeepfakeDebug = useCallback(async () => {
    if (!debugFile) { setError('Choose a WAV or decodable MP3 file first.'); return; }
    try { const form = new FormData(); form.append('audio', debugFile); const response = await fetch(`${API_URL}/api/debug/deepfake`, { method: 'POST', body: form }); const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'Debug analysis failed.'); setDebugResult(result); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Debug analysis failed.'); }
  }, [debugFile]);
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [live]);

  const applyUpdate = useCallback((update: AnalysisUpdate) => {
    setSessionId(update.session_id); setTrust(update.trust_score); setBand(update.trust_band);
    setPolicy(update.policy_decision); setPolicyReasons(update.policy_reasons); setAttack(update.attack_chain || null);
    setHealth(update.model_health); setEvents((current) => [...update.events, ...current].slice(0, 60));
    if (update.transcript.text) setTranscript((current) => [...current, { timestamp: update.timestamp, text: update.transcript.text, confidence: update.transcript.confidence }]);
    setTimeline((current) => [...current, { time: Math.round(update.timestamp), trust: update.trust_score }].slice(-30));
    setSignals({
      synthetic: update.signals.synthetic_voice_risk.synthetic_score,
      speaker: update.signals.speaker.speaker_similarity === null ? null : 1 - update.signals.speaker.speaker_similarity,
      liveness: update.signals.liveness.liveness_risk,
      context: update.context.context_risk,
      action: update.context.action_risk,
      quality: update.signals.audio_quality?.score ?? 1,
    });
  }, []);

  const connect = useCallback(async () => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return socketRef.current;
    const url = sessionId ? `${WS_URL}?session_id=${encodeURIComponent(sessionId)}` : WS_URL;
    const socket = new WebSocket(url); socket.binaryType = 'arraybuffer'; socketRef.current = socket;
    await new Promise<void>((resolve, reject) => {
      socket.onopen = () => resolve(); socket.onerror = () => reject(new Error('Cannot connect to the V.O.I.C.E. backend on port 8000.'));
    });
    socket.onmessage = (message) => {
      const data = JSON.parse(message.data);
      if (data.type === 'session_started') setSessionId(data.session_id);
      else if (data.type === 'analysis_update') applyUpdate(data);
      else if (data.type === 'challenge_created') { setChallenge(data.phrase); setChallengeInput(''); }
      else if (data.type === 'error') setError(data.message);
    };
    socket.onclose = () => setLive(false);
    return socket;
  }, [applyUpdate, sessionId]);

  const start = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const socket = await connect();
      if (selectedSpeaker) socket.send(JSON.stringify({ type: 'configure', speaker_id: selectedSpeaker }));
      audioRef.current = await startPcmStream((chunk) => { if (socket.readyState === WebSocket.OPEN) socket.send(chunk); });
      setLive(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Microphone start failed.'); }
    finally { setBusy(false); }
  }, [connect, selectedSpeaker]);

  const stop = useCallback(async () => {
    await audioRef.current?.stop(); audioRef.current = null;
    if (socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send(JSON.stringify({ type: 'stop' }));
    socketRef.current = null; setLive(false);
  }, []);

  const analyzeManual = useCallback(async (text: string) => {
    setBusy(true); setError(null);
    try {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: 'manual_transcript', text }));
      } else {
        const response = await fetch(`${API_URL}/api/analyze-context`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ transcript: text, session_id: sessionId }) });
        if (!response.ok) throw new Error('Context analysis request failed.');
        applyUpdate(await response.json());
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Analysis failed.'); }
    finally { setBusy(false); }
  }, [applyUpdate, sessionId]);

  const startChallenge = useCallback(async () => {
    try { const socket = await connect(); socket.send(JSON.stringify({ type: 'challenge' })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Challenge failed.'); }
  }, [connect, selectedSpeaker]);

  const submitChallenge = useCallback(async () => {
    await analyzeManual(challengeInput); setChallenge(null);
  }, [analyzeManual, challengeInput]);

  const createIncident = useCallback(async () => {
    if (!sessionId) { setError('Analyze at least one segment before creating an incident.'); return; }
    try {
      const response = await fetch(`${API_URL}/api/incidents/${sessionId}`, { method: 'POST' });
      if (!response.ok) throw new Error('Incident generation failed.');
      setIncident(await response.json());
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Incident generation failed.'); }
  }, [sessionId]);

  const reset = useCallback(async () => {
    await stop(); setSessionId(null); setElapsed(0); setTrust(88); setBand('TRUSTED'); setPolicy('ALLOW'); setPolicyReasons(['No material threat condition met']); setAttack(null); setTranscript([]); setEvents([]); setTimeline([{ time: 0, trust: 88 }]); setHealth(initialHealth); setSignals({ synthetic: null, speaker: null, liveness: null, context: 0, action: 0, quality: 1 }); setError(null); setIncident(null);
  }, [stop]);

  useEffect(() => {
    const context = (document as Document & { modelContext?: { registerTool: (tool: unknown, options?: { signal: AbortSignal }) => void | Promise<void> } }).modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    void Promise.resolve(context.registerTool({ name: 'analyze_voice_scenario', title: 'Analyze voice scenario', description: 'Analyze a supplied call transcript and update the visible V.O.I.C.E. risk dashboard.', inputSchema: { type: 'object', properties: { transcript: { type: 'string', minLength: 1 } }, required: ['transcript'], additionalProperties: false }, annotations: { readOnlyHint: false, untrustedContentHint: true }, execute: async (input: unknown) => { const value = input as { transcript?: string }; if (!value.transcript?.trim()) throw new Error('transcript is required'); await analyzeManual(value.transcript); return { status: 'submitted' }; } }, { signal: lifecycle.signal })).catch(() => undefined);
    return () => lifecycle.abort();
  }, [analyzeManual]);

  const riskRows = useMemo(() => [
    ['Synthetic voice risk', signals.synthetic, signals.synthetic === null ? 'UNKNOWN' : undefined],
    ['Speaker mismatch', signals.speaker, signals.speaker === null ? 'UNKNOWN' : undefined],
    ['Liveness / replay risk', signals.liveness, signals.liveness === null ? 'UNKNOWN' : undefined],
    ['Context risk', signals.context, undefined], ['Action risk', signals.action, undefined], ['Audio quality', signals.quality, 'QUALITY'],
  ] as [string, number | null, string | undefined][], [signals]);
  const danger = trust < 25; const warning = trust < 50;

  return (
    <div className="min-h-screen bg-[#06020f] text-[#f3f1f7] lg:flex">
      <aside className="border-b border-white/5 bg-[#0e0a1a] p-4 lg:sticky lg:top-0 lg:h-screen lg:w-[248px] lg:shrink-0 lg:border-b-0 lg:border-r lg:p-5">
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-3 px-2 py-2"><Logo /><div><div className="text-base font-bold tracking-wide">V.O.I.C.E.</div><div className="text-[11px] uppercase tracking-[.16em] text-purple-400">Security Vault</div></div></div>
          <nav className="mt-7 flex gap-2 overflow-x-auto lg:flex-col" aria-label="Primary navigation">
            <NavItem active icon={<Gauge />} label="Live Dashboard" /><NavItem icon={<Radar />} label="Threat Monitoring" /><NavItem icon={<FileWarning />} label="Incident Vault" /><NavItem icon={<Fingerprint />} label="Speaker Identity" onClick={() => setSpeakerDialog(true)} />
          </nav>
          <div className="mt-auto hidden space-y-3 border-t border-white/5 pt-5 lg:block">
            <div className="rounded-lg bg-[#141026] p-3 text-xs leading-5 text-[#8d87a3]"><span className="mb-1 block font-semibold text-emerald-400">PRIVACY MODE: ON</span>Raw microphone audio is processed transiently and not retained.</div>
            <div className="flex items-center gap-2 px-2 text-xs text-[#8d87a3]"><Bell className="size-4" /> Security notifications active</div>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="border-b border-white/5 bg-[#0c0816]/95 px-5 py-5 lg:px-8">
          <div className="mx-auto flex max-w-[1540px] flex-wrap items-center justify-between gap-4">
            <div><p className="text-xs text-[#8d87a3]">Command Center / Live Analysis</p><h1 className="mt-1 text-2xl font-semibold">Zero-Trust Voice Gateway</h1></div>
            <div className="flex flex-wrap items-center gap-3">
              <select aria-label="Claimed trusted speaker" value={selectedSpeaker} onChange={(event) => setSelectedSpeaker(event.target.value)} className="rounded-full border border-white/10 bg-[#141026] px-3 py-2 text-xs text-slate-200"><option value="">Claimed speaker: none</option>{speakers.map((speaker) => <option key={speaker} value={speaker}>{speaker}</option>)}</select><span className={`status-pill ${live ? 'online' : ''}`}><span className="status-dot" />{live ? 'LIVE ANALYSIS' : 'SYSTEM READY'}</span>
              <span className="rounded-full border border-white/8 bg-[#141026] px-4 py-2 font-mono text-xs text-[#8d87a3]">{sessionId ? `ID ${sessionId.toUpperCase()}` : 'NO SESSION'} · {formatTime(elapsed)}</span>
            </div>
          </div>
        </header>

        <div className="mx-auto max-w-[1540px] space-y-5 p-4 lg:p-7">
          {error && <div role="alert" className="flex items-center justify-between rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-300"><span>{error}</span><button onClick={() => setError(null)} aria-label="Dismiss error">×</button></div>}

          <section className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
            <Card>
              <div className="protection-layout">
                <div className="radial-progress" style={{ background: `conic-gradient(${danger ? '#ef4444' : warning ? '#eab308' : '#a855f7'} ${trust}%, rgba(255,255,255,.05) 0)` }}><div className="radial-inner"><strong>{Math.round(trust)}</strong><span>TRUST SCORE</span></div></div>
                <div className="min-w-0 flex-1"><div className="metric-title">CONTINUOUS VOICE TRUST FUSION</div><div className="flex flex-wrap items-center gap-3"><h2 className="text-2xl font-semibold">Current trust posture</h2><Badge className={bandClass(band)}>{band}</Badge></div><p className="mt-2 text-sm leading-6 text-[#8d87a3]">Explainable fusion of voice authenticity, identity, replay evidence, conversation context, requested action, and signal quality.</p><div className="mt-4 flex flex-wrap gap-6 border-t border-white/5 pt-4 text-sm"><Metric label="POLICY DECISION" value={policy} tone={policy.includes('BLOCK') ? 'danger' : policy.includes('HOLD') || policy.includes('VERIFY') ? 'warning' : 'good'} /><Metric label="ATTACK CHAIN" value={attack || 'NONE OBSERVED'} /><Metric label="EVENTS" value={String(events.length)} /></div></div>
              </div>
            </Card>
            <Card>
              <div className="section-heading"><div><p className="eyebrow">VOICE CHANNEL</p><h2>Live activity monitor</h2></div><span className={`flex items-center gap-2 text-xs font-semibold ${live ? 'text-emerald-400' : 'text-[#8d87a3]'}`}><span className={`size-2 rounded-full ${live ? 'animate-pulse bg-emerald-400 shadow-[0_0_8px_#22c55e]' : 'bg-slate-600'}`} />{live ? 'LISTENING' : 'IDLE'}</span></div>
              <Waveform active={live} />
              <div className="mt-4 flex flex-wrap gap-2"><Button onClick={live ? stop : start} disabled={busy} className={live ? 'bg-red-500 text-white hover:bg-red-400' : 'bg-purple-500 text-white hover:bg-purple-400'}>{live ? <><CircleStop /> Stop Analysis</> : <><Mic /> {busy ? 'Connecting…' : 'Start Analysis'}</>}</Button><Button variant="outline" onClick={startChallenge} className="border-purple-500/30 bg-transparent text-purple-200 hover:bg-purple-500/10"><LockKeyhole /> Challenge Caller</Button><Button variant="outline" onClick={createIncident} className="border-white/10 bg-transparent text-slate-200"><FileWarning /> Create Incident</Button><Button variant="outline" onClick={() => setDebugDialog(true)} className="border-white/10 bg-transparent text-slate-200"><TerminalSquare /> Test audio</Button><Button variant="ghost" onClick={reset} className="text-[#8d87a3]"><RefreshCw /> Reset</Button></div>
            </Card>
          </section>

          <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {riskRows.map(([label, value, special]) => <RiskCard key={label} label={label} value={value} special={special} />)}
          </section>

          <section className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
            <div className="space-y-5">
              <Card>
                <div className="section-heading"><div><p className="eyebrow">REAL-TIME ASR</p><h2>Live transcript</h2></div><Headphones className="size-5 text-purple-400" /></div>
                <div className="transcript-box">
                  {transcript.length ? transcript.map((item, index) => <div className="transcript-row" key={`${item.timestamp}-${index}`}><span className="timestamp">{formatTime(Math.round(item.timestamp))}</span><p>{highlight(item.text)}</p><span className="confidence">{Math.round(item.confidence * 100)}%</span></div>) : <Empty icon={<AudioLines />} text="Microphone and manual scenario transcripts will appear here." />}
                </div>
                <div className="mt-4"><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#8d87a3]">Manual test scenarios</p><div className="flex flex-wrap gap-2">{scenarios.map(([label, text]) => <Button key={label} size="sm" variant="outline" disabled={busy} onClick={() => analyzeManual(text)} className="border-white/10 bg-[#141026] text-xs text-slate-300 hover:border-purple-500/50 hover:bg-purple-500/10">{label === 'Normal' ? <Play /> : <Siren />} {label}</Button>)}</div></div>
              </Card>
              <Card>
                <div className="section-heading"><div><p className="eyebrow">TEMPORAL RISK</p><h2>Trust timeline</h2></div><Activity className="size-5 text-purple-400" /></div>
                <div className="h-56 min-w-0"><ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 640, height: 224 }}><AreaChart data={timeline}><defs><linearGradient id="trustFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#a855f7" stopOpacity={.48}/><stop offset="100%" stopColor="#a855f7" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#241a3d" strokeDasharray="3 3" vertical={false}/><XAxis dataKey="time" stroke="#6d6785" fontSize={11} tickFormatter={(v) => `${v}s`}/><YAxis domain={[0,100]} stroke="#6d6785" fontSize={11}/><Tooltip contentStyle={{ background:'#140e2b', border:'1px solid #2e235c', borderRadius:8 }} /><Area type="monotone" dataKey="trust" stroke="#a855f7" strokeWidth={2} fill="url(#trustFill)" /></AreaChart></ResponsiveContainer></div>
              </Card>
            </div>

            <div className="space-y-5">
              <Card>
                <div className="section-heading"><div><p className="eyebrow">POLICY ENGINE</p><h2>Recommended security action</h2></div><ShieldCheck className="size-5 text-purple-400" /></div>
                <div className={`policy-box ${policyTone(policy)}`}><div className="font-mono text-2xl font-bold">{policy}</div>{policyReasons.map((reason) => <p key={reason}>• {reason}</p>)}</div>
              </Card>
              <Card>
                <div className="section-heading"><div><p className="eyebrow">SECURITY EVENTS</p><h2>Threat activity</h2></div><ShieldAlert className="size-5 text-purple-400" /></div>
                <div className="max-h-[430px] space-y-2 overflow-y-auto pr-1">{events.length ? events.map((event, index) => <div key={`${event.event_hash}-${index}`} className={`event-row severity-${event.severity.toLowerCase()}`}><div><h3>{event.event.replaceAll('_',' ')}</h3><p>{formatTime(Math.round(event.timestamp))} · {event.source} · {Math.round(event.confidence * 100)}% confidence</p></div><span>{event.severity}</span></div>) : <Empty icon={<ShieldCheck />} text="No security events in this session." />}</div>
              </Card>
              <Card>
                <div className="section-heading"><div><p className="eyebrow">MODEL HEALTH</p><h2>Detection subsystems</h2></div><TerminalSquare className="size-5 text-purple-400" /></div>
                <div className="space-y-3">{Object.entries(health).map(([name, status]) => <div key={name} className="flex items-center justify-between border-b border-white/5 pb-2 text-sm"><span className="text-slate-300">{name}</span><span className={status === 'ONLINE' ? 'text-emerald-400' : status === 'UNAVAILABLE' || status === 'OFFLINE' ? 'text-red-400' : 'text-amber-300'}>{status}</span></div>)}</div>
              </Card>
            </div>
          </section>
          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/5 py-4 text-xs text-[#6d6785]"><span>V.O.I.C.E. analytical engine · Local zero-trust prototype</span><span>Raw audio retention: OFF · Event integrity: SHA-256 chain</span></footer>
        </div>
      </main>

      <Dialog open={speakerDialog} onOpenChange={setSpeakerDialog}><DialogContent className="border border-purple-500/25 bg-[#140e2b] text-white sm:max-w-lg"><DialogHeader><DialogTitle>Speaker Identity</DialogTitle><DialogDescription>Add a trusted speaker with approximately 15–30 seconds of clear speech. The ECAPA threshold is configurable and is not presented as calibrated.</DialogDescription></DialogHeader><Input value={speakerIdInput} onChange={(event) => setSpeakerIdInput(event.target.value)} placeholder="Name or trusted speaker ID" className="border-[#2e235c] bg-[#0b071a]" /><p className="text-sm text-purple-200">Recorded: {enrollmentSeconds}s / 15–30s recommended</p>{enrollmentResult && <p className="rounded bg-emerald-500/10 p-3 text-sm text-emerald-300">{enrollmentResult}</p>}<DialogFooter>{enrolling ? <Button onClick={finishEnrollment} className="bg-red-500 hover:bg-red-400"><CircleStop /> Stop & enroll</Button> : <Button onClick={startEnrollment} className="bg-purple-500 hover:bg-purple-400"><Mic /> Record trusted speaker</Button>}</DialogFooter></DialogContent></Dialog>
      <Dialog open={debugDialog} onOpenChange={setDebugDialog}><DialogContent className="border border-purple-500/25 bg-[#140e2b] text-white sm:max-w-lg"><DialogHeader><DialogTitle>Deepfake model test</DialogTitle><DialogDescription>Runs the configured local classifier on this file. Output is a model result, not a scientific accuracy measurement.</DialogDescription></DialogHeader><Input type="file" accept="audio/wav,audio/mpeg,.wav,.mp3" onChange={(event) => setDebugFile(event.target.files?.[0] || null)} className="border-[#2e235c] bg-[#0b071a]" />{debugResult && <pre className="max-h-64 overflow-auto rounded bg-[#090518] p-3 text-xs text-purple-200">{JSON.stringify(debugResult, null, 2)}</pre>}<DialogFooter><Button onClick={runDeepfakeDebug} className="bg-purple-500 hover:bg-purple-400">Run local model</Button></DialogFooter></DialogContent></Dialog>      <Dialog open={Boolean(challenge)} onOpenChange={(open) => !open && setChallenge(null)}><DialogContent className="border border-purple-500/25 bg-[#140e2b] text-white sm:max-w-md"><DialogHeader><DialogTitle>Active caller challenge</DialogTitle><DialogDescription>This phrase is additional evidence—not a guarantee of liveness. Ask the caller to repeat it exactly.</DialogDescription></DialogHeader><div className="rounded-lg border border-purple-500/30 bg-[#090518] p-5 text-center font-mono text-2xl tracking-[.16em] text-purple-300">{challenge}</div><Input value={challengeInput} onChange={(event) => setChallengeInput(event.target.value)} placeholder="Transcribed or typed response" className="border-[#2e235c] bg-[#0b071a]" /><DialogFooter><Button onClick={submitChallenge} disabled={!challengeInput.trim()} className="bg-purple-500 hover:bg-purple-400">Verify response</Button></DialogFooter></DialogContent></Dialog>
      <Dialog open={Boolean(incident)} onOpenChange={(open) => !open && setIncident(null)}><DialogContent className="max-h-[85vh] overflow-auto border border-purple-500/25 bg-[#140e2b] text-white sm:max-w-2xl"><DialogHeader><DialogTitle>Incident report created</DialogTitle><DialogDescription>Tamper-evident security metadata was stored locally. Raw audio was not included.</DialogDescription></DialogHeader><pre className="overflow-auto rounded-lg bg-[#090518] p-4 text-xs leading-5 text-purple-200">{JSON.stringify(incident, null, 2)}</pre></DialogContent></Dialog>
    </div>
  );
}

function Logo() { return <div className="grid size-10 place-items-center bg-gradient-to-br from-purple-500 to-indigo-500 [clip-path:polygon(50%_0%,100%_25%,100%_75%,50%_100%,0%_75%,0%_25%)]"><AudioLines className="size-5 text-white" /></div>; }
function NavItem({ icon, label, active = false, onClick }: { icon: React.ReactNode; label: string; active?: boolean; onClick?: () => void }) { return <button onClick={onClick} className={`flex shrink-0 items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition lg:w-full ${active ? 'bg-purple-500/15 text-white shadow-[inset_0_0_12px_rgba(168,85,247,.08)]' : 'text-[#8d87a3] hover:bg-white/3 hover:text-white'}`}>{icon}<span>{label}</span></button>; }
function Card({ children }: { children: React.ReactNode }) { return <section className="rounded-xl border border-white/[.055] bg-[#0e0a1a] p-5 shadow-[0_18px_50px_rgba(0,0,0,.14)]">{children}</section>; }
function Metric({ label, value, tone }: { label: string; value: string; tone?: 'danger' | 'warning' | 'good' }) { return <div><span className="block text-[10px] tracking-widest text-[#6d6785]">{label}</span><strong className={`mt-1 block text-sm ${tone === 'danger' ? 'text-red-400' : tone === 'warning' ? 'text-amber-300' : tone === 'good' ? 'text-emerald-400' : 'text-white'}`}>{value}</strong></div>; }
function RiskCard({ label, value, special }: { label: string; value: number | null; special?: string }) { const display = value === null ? 'UNKNOWN' : special === 'QUALITY' ? `${Math.round(value*100)}%` : `${Math.round(value*100)}%`; const tone = value !== null && (special === 'QUALITY' ? value < .55 : value > .65) ? 'red' : value !== null && (special === 'QUALITY' ? value < .8 : value > .35) ? 'amber' : 'purple'; return <div className="rounded-lg border border-white/[.055] bg-[#0e0a1a] p-4"><div className="mb-3 min-h-8 text-[11px] uppercase leading-4 tracking-[.08em] text-[#8d87a3]">{label}</div><div className={`text-xl font-bold ${tone === 'red' ? 'text-red-400' : tone === 'amber' ? 'text-amber-300' : 'text-purple-300'}`}>{display}</div><Progress value={value === null ? 0 : value * 100} className={`mt-3 h-1 bg-[#241a3d] ${tone === 'red' ? '[&_[data-slot=progress-indicator]]:bg-red-500' : tone === 'amber' ? '[&_[data-slot=progress-indicator]]:bg-amber-400' : '[&_[data-slot=progress-indicator]]:bg-purple-500'}`} /></div>; }
function Waveform({ active }: { active: boolean }) { return <div className="waveform">{Array.from({length:48}, (_, index) => <span key={index} className={active ? 'active' : ''} style={{ height: `${active ? 14 + ((index * 17) % 52) : 7}px`, animationDelay: `${index * -35}ms` }} />)}<div className="wave-grid" /></div>; }
function Empty({ icon, text }: { icon: React.ReactNode; text: string }) { return <div className="grid min-h-36 place-items-center text-center text-sm text-[#6d6785]"><div><span className="mx-auto mb-3 grid place-items-center [&>svg]:mx-auto [&>svg]:size-7">{icon}</span>{text}</div></div>; }
function formatTime(seconds: number) { return `${String(Math.floor(seconds / 60)).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')}`; }
function highlight(text: string) { const keyword = new RegExp(suspicious.source, 'i'); return text.split(suspicious).map((part, index) => keyword.test(part) ? <mark key={index}>{part}</mark> : part); }
function bandClass(value: string) { return value === 'CRITICAL' ? 'border-red-500/30 bg-red-500/10 text-red-300' : value === 'VERIFY' ? 'border-amber-400/30 bg-amber-400/10 text-amber-200' : value === 'MONITOR' ? 'border-blue-400/30 bg-blue-400/10 text-blue-200' : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'; }
function policyTone(value: string) { return value.includes('BLOCK') ? 'critical' : value.includes('HOLD') || value.includes('VERIFY') ? 'warning' : value === 'MONITOR' ? 'monitor' : 'allow'; }
