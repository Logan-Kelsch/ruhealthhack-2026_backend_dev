import { useEffect, useRef, useState } from "react";
import type { Go } from "../../app/types";
import { MicIcon } from "../../components/Icons";
import { BuildTag, Page } from "../../components/ui";

type MicState = "asking" | "live" | "blocked";

const RING = 2 * Math.PI * 118;

// Practice screen before the visit. The ring and bars follow the real microphone level.
// There is no text box: the encounter itself stays hands-free.
export function MicCheck({ go }: { go: Go }) {
  const [state, setState] = useState<MicState>("asking");
  const [level, setLevel] = useState(0);
  const [muted, setMuted] = useState(false);
  const stream = useRef<MediaStream | null>(null);

  useEffect(() => {
    let frame = 0;
    let context: AudioContext | null = null;
    let stopped = false;

    navigator.mediaDevices
      ?.getUserMedia({ audio: true })
      .then((media) => {
        if (stopped) return media.getTracks().forEach((track) => track.stop());
        stream.current = media;
        context = new AudioContext();
        const analyser = context.createAnalyser();
        analyser.fftSize = 512;
        context.createMediaStreamSource(media).connect(analyser);
        const samples = new Float32Array(analyser.fftSize);
        let smooth = 0;
        const read = () => {
          analyser.getFloatTimeDomainData(samples);
          let sum = 0;
          for (const value of samples) sum += value * value;
          // Speech RMS sits around 0.02–0.2, so scale it up and ease it so the ring doesn't flicker.
          const rms = Math.min(1, Math.sqrt(sum / samples.length) * 6);
          smooth = smooth * 0.8 + rms * 0.2;
          setLevel(smooth);
          frame = requestAnimationFrame(read);
        };
        read();
        setState("live");
      })
      .catch(() => setState("blocked"));
    if (!navigator.mediaDevices) setState("blocked");

    return () => {
      stopped = true;
      cancelAnimationFrame(frame);
      stream.current?.getTracks().forEach((track) => track.stop());
      void context?.close();
    };
  }, []);

  function toggleMute() {
    const next = !muted;
    stream.current?.getAudioTracks().forEach((track) => (track.enabled = !next));
    setMuted(next);
  }

  const shown = muted ? 0 : level;
  const note =
    state === "asking"
      ? "Allow microphone access when your browser asks."
      : state === "blocked"
        ? "Microphone blocked. Allow it in your browser, then reload."
        : muted
          ? "Muted"
          : shown > 0.08
            ? "We can hear you"
            : "Say a few words";

  return (
    <Page>
      <div className="mx-auto flex w-full max-w-[720px] flex-col items-center gap-6 pt-4 pb-6 text-center">
        <div>
          <h1 className="m-0 font-serif text-[clamp(40px,4vw,62px)] leading-none font-normal tracking-[-1.4px]">Mic check before your visit</h1>
          <p className="mt-3 font-serif text-[clamp(18px,1.6vw,24px)] text-ink-soft">Speak a few words to make sure your microphone is working.</p>
        </div>

        <div className="relative flex size-[300px] items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-indigo-soft/70" style={{ transform: `scale(${0.94 + shown * 0.08})` }} />
          <svg viewBox="0 0 260 260" className="absolute inset-[20px] -rotate-90" aria-hidden>
            <circle cx="130" cy="130" r="118" fill="none" stroke="#d6defb" strokeWidth="14" />
            <circle
              cx="130"
              cy="130"
              r="118"
              fill="none"
              stroke="url(#mic-arc)"
              strokeWidth="14"
              strokeLinecap="round"
              strokeDasharray={RING}
              strokeDashoffset={RING * (1 - Math.max(0.03, shown))}
              style={{ transition: "stroke-dashoffset 90ms linear" }}
            />
            <defs>
              <linearGradient id="mic-arc" x1="0" x2="1">
                <stop offset="0" stopColor="#7d8fe6" />
                <stop offset="1" stopColor="#4a5fd9" />
              </linearGradient>
            </defs>
          </svg>
          <div className={`relative flex size-[176px] items-center justify-center rounded-full bg-card shadow-[0_10px_30px_-18px_rgba(25,31,92,.5)] ${muted || state !== "live" ? "text-inactive" : "text-indigo"}`}>
            <MicIcon size={72} />
          </div>
        </div>

        <div className="flex h-[66px] w-full max-w-[540px] items-center justify-between gap-4 rounded-xl border border-indigo-line/60 bg-card px-7">
          <span className={`font-serif ${state === "live" ? "text-[clamp(18px,1.8vw,26px)]" : "text-[18px]"} ${state === "blocked" ? "text-danger" : ""}`}>{note}</span>
          <span className="flex h-8 items-end gap-[5px]" aria-hidden>
            {[0.25, 0.4, 0.6, 0.8, 1, 0.7].map((step, index) => (
              <span
                key={index}
                className="w-[5px] rounded-full transition-[height,background] duration-100"
                style={{ height: `${Math.max(18, step * 100)}%`, background: shown >= step * 0.45 ? "#4a5fd9" : "#cdd5f6" }}
              />
            ))}
          </span>
        </div>
        <BuildTag kind="planned" feature="E-03 live captions" />

        <div className="flex items-center gap-4 font-serif text-[18px]">
          <span className="flex size-12 items-center justify-center rounded-full bg-indigo-soft text-ink">
            <HeadphonesIcon />
          </span>
          Headphones recommended, so the patient’s voice doesn’t echo.
        </div>

        <button
          type="button"
          onClick={toggleMute}
          aria-pressed={muted}
          className="flex w-full max-w-[680px] items-center gap-5 rounded-xl border border-line bg-wash px-12 py-4 text-left font-serif text-[18px] hover:bg-indigo-soft/50"
        >
          <span className={`relative h-8 w-[58px] shrink-0 rounded-full transition-colors ${muted ? "bg-indigo" : "bg-line-4"}`}>
            <span className={`absolute top-1 size-6 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,.3)] transition-[left] ${muted ? "left-[30px]" : "left-1"}`} />
          </span>
          <MicOffIcon />
          You can mute any time. There is no typing during the visit.
        </button>

        <button
          type="button"
          onClick={() => go("s-encounter")}
          className="h-[60px] w-[260px] rounded-xl bg-bright font-serif text-[24px] text-white shadow-[0_14px_30px_-16px_rgba(74,95,217,.9)] hover:bg-indigo"
        >
          I’m ready
        </button>
      </div>
    </Page>
  );
}

function HeadphonesIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M4 15v-3a8 8 0 0 1 16 0v3" />
      <rect x="3" y="14" width="4.5" height="7" rx="1.6" fill="currentColor" />
      <rect x="16.5" y="14" width="4.5" height="7" rx="1.6" fill="currentColor" />
    </svg>
  );
}

function MicOffIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M3 3l18 18" />
    </svg>
  );
}
