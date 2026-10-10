import { useEffect, useRef } from "react";
import gsap from "gsap";
import { BuildTag } from "./ui";

// 16:9 "video call" frame for the patient. Iteration 1 has no video, so the frame opens from a
// watercolor disc into a call and a painted head-and-shoulders silhouette fades in. It breathes
// while listening and glows while the patient speaks. Tavus video replaces the silhouette in iteration 2.
export function PatientCall({
  name,
  speaking,
  muted,
  listening,
}: {
  name: string;
  speaking: boolean;
  muted: boolean;
  listening: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  const halo = useRef<gsap.core.Tween | null>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const q = gsap.utils.selector(el);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const ctx = gsap.context(() => {
      if (reduce) {
        gsap.set(q(".pc-wash, .pc-connect"), { autoAlpha: 0 });
        return;
      }
      const box = el.getBoundingClientRect();
      const disc = Math.min(box.height * 0.62, 220);
      const tl = gsap.timeline({ defaults: { ease: "power3.inOut" } });
      tl.from(q(".pc-frame"), { width: disc, height: disc, borderRadius: disc / 2, duration: 1.1, delay: 0.25, clearProps: "width,height,borderRadius" })
        .from(q(".pc-room"), { autoAlpha: 0, scale: 1.12, duration: 1.2, ease: "power2.out" }, "-=0.55")
        .to(q(".pc-connect"), { autoAlpha: 0, y: -8, duration: 0.4 }, "-=0.6")
        .from(q(".pc-figure"), { autoAlpha: 0, yPercent: 14, filter: "blur(14px)", duration: 1.3, ease: "power2.out", clearProps: "filter" }, "-=0.5")
        .to(q(".pc-wash"), { autoAlpha: 0, duration: 1.1, ease: "power1.out" }, "<0.2")
        .from(q(".pc-chrome"), { autoAlpha: 0, y: 6, stagger: 0.08, duration: 0.45, ease: "power2.out" }, "-=0.6")
        .add(() => {
          gsap.to(q(".pc-body"), { scaleY: 1.014, scaleX: 1.006, transformOrigin: "50% 100%", duration: 2.8, ease: "sine.inOut", yoyo: true, repeat: -1 });
          gsap.to(q(".pc-head"), { y: -1.2, duration: 2.8, ease: "sine.inOut", yoyo: true, repeat: -1 });
        });
    }, el);
    return () => ctx.revert();
  }, []);

  // The halo pulses only while the patient is speaking.
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const glow = el.querySelector(".pc-halo");
    halo.current?.kill();
    if (speaking && !muted) {
      gsap.to(glow, { autoAlpha: 0.9, duration: 0.35 });
      halo.current = gsap.to(glow, { scale: 1.08, duration: 0.55, ease: "sine.inOut", yoyo: true, repeat: -1 });
    } else {
      gsap.to(glow, { autoAlpha: 0, scale: 1, duration: 0.5 });
    }
  }, [speaking, muted]);

  return (
    <div ref={root} className="relative flex aspect-video w-full items-center justify-center">
      <div className="pc-frame relative h-full w-full overflow-hidden rounded-[18px] shadow-[0_24px_60px_-30px_rgba(25,31,92,.55)] ring-1 ring-white/70">
        <div className="pc-room absolute inset-0 bg-[#e9e4ee] bg-[url(/assets/room.jpg)] bg-cover bg-center" />
        <svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMax meet" className="pc-figure absolute inset-0 h-full w-full" aria-hidden>
          <defs>
            <linearGradient id="pc-skin" x1="0" y1="0" x2="0.4" y2="1">
              <stop offset="0" stopColor="#aeb5f0" />
              <stop offset="0.55" stopColor="#8a8fe0" />
              <stop offset="1" stopColor="#c29ad6" />
            </linearGradient>
            <radialGradient id="pc-glow">
              <stop offset="0" stopColor="#ffd8a8" stopOpacity="0.95" />
              <stop offset="0.6" stopColor="#f6b2a4" stopOpacity="0.35" />
              <stop offset="1" stopColor="#f6b2a4" stopOpacity="0" />
            </radialGradient>
            <filter id="pc-paint" x="-10%" y="-10%" width="120%" height="120%">
              <feTurbulence type="fractalNoise" baseFrequency="0.09" numOctaves="3" seed="7" />
              <feDisplacementMap in="SourceGraphic" scale="2.6" />
              <feGaussianBlur stdDeviation="0.7" />
            </filter>
          </defs>
          <ellipse className="pc-halo" cx="80" cy="50" rx="44" ry="40" fill="url(#pc-glow)" opacity="0" style={{ transformOrigin: "80px 50px" }} />
          <g filter="url(#pc-paint)" opacity="0.82" style={{ mixBlendMode: "multiply" }}>
            <path className="pc-body" d="M38 92 C40 72 56 63 72 61 L74 54 L86 54 L88 61 C104 63 120 72 122 92 Z" fill="url(#pc-skin)" />
            <ellipse className="pc-head" cx="80" cy="39" rx="13" ry="15.5" fill="url(#pc-skin)" />
          </g>
        </svg>
        <div className="pc-wash absolute inset-0 bg-[url(/assets/bloom.jpg)] bg-[length:240%_auto] bg-[position:30%_30%]" />
        <div className="pc-connect absolute inset-0 flex items-center justify-center">
          <span className="rounded-full bg-white/80 px-4 py-1.5 font-serif text-[17px] text-ink backdrop-blur-sm">Connecting…</span>
        </div>

        <span className="pc-chrome absolute top-3.5 left-3.5 inline-flex h-8 items-center gap-2 rounded-full bg-[#141a55]/55 px-3 font-sans text-[13px] text-white backdrop-blur-md">
          <span className={`size-2 rounded-full ${listening ? "rnd-blink bg-[#ff6b5e]" : "bg-white/60"}`} />
          {listening ? "Mic live" : "Mic off"}
        </span>
        <span className="pc-chrome absolute right-3.5 bottom-3.5">
          <BuildTag kind="planned" feature="E-15 video" className="bg-white/85 backdrop-blur-sm" />
        </span>
        <span className="pc-chrome absolute bottom-3.5 left-3.5 inline-flex h-8 items-center gap-2 rounded-full bg-white/80 px-3 font-sans text-[13px] text-ink backdrop-blur-sm">
          <Bars on={speaking && !muted} />
          {speaking ? `${name} is speaking` : muted ? "Paused while muted" : listening ? "Listening to you" : "Waiting for your microphone"}
        </span>
      </div>
    </div>
  );
}

function Bars({ on }: { on: boolean }) {
  return (
    <span className="flex h-3.5 items-end gap-[2px]" aria-hidden>
      {[0.5, 1, 0.7].map((height, index) => (
        <span
          key={index}
          className={`w-[3px] rounded-full ${on ? "rnd-eq bg-indigo" : "bg-inactive"}`}
          style={{ height: on ? `${height * 100}%` : "30%", animationDelay: `${index * 0.15}s` }}
        />
      ))}
    </span>
  );
}
