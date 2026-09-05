export type AudioStreamHandle = {
  stop: () => Promise<void>;
  analyser: AnalyserNode;
};

export async function startPcmStream(onChunk: (chunk: ArrayBuffer) => void): Promise<AudioStreamHandle> {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone capture is unavailable in this browser.');
  const request = navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false });
  const timeout = new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error('Microphone permission timed out. Allow microphone access for localhost and retry.')), 10000));
  const stream = await Promise.race([request, timeout]);
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const analyser = context.createAnalyser();
  analyser.fftSize = 1024;
  const processor = context.createScriptProcessor(4096, 1, 1);
  const chunks: number[] = [];

  processor.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0);
    const ratio = context.sampleRate / 16000;
    for (let outputIndex = 0; outputIndex < input.length / ratio; outputIndex += 1) {
      const start = Math.floor(outputIndex * ratio);
      const end = Math.min(input.length, Math.floor((outputIndex + 1) * ratio));
      let sum = 0;
      for (let index = start; index < end; index += 1) sum += input[index];
      chunks.push(Math.max(-1, Math.min(1, sum / Math.max(1, end - start))));
    }
    if (chunks.length >= 32000) {
      const pcm = new Int16Array(chunks.splice(0, 32000).map((sample) => sample < 0 ? sample * 32768 : sample * 32767));
      onChunk(pcm.buffer);
    }
  };

  source.connect(analyser);
  analyser.connect(processor);
  processor.connect(context.destination);
  return {
    analyser,
    stop: async () => {
      processor.disconnect(); analyser.disconnect(); source.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      await context.close();
    },
  };
}
