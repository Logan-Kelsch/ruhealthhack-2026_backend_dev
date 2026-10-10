import { gsap } from "gsap";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

export type Role = "faculty" | "student";

type Origin = { x: number; y: number };
type Play = (role: Role, origin: Origin, swap: () => void) => void;

const COPY: Record<Role, { title: string; line: string }> = {
  faculty: { title: "Faculty", line: "Build patients, assign cases, see where your class struggles." },
  student: { title: "Student", line: "Talk with your patient, then see what you found and missed." },
};

const ModeContext = createContext<Play | null>(null);

// Screens ask for a role change through this hook; the provider owns the animation.
export function useModeSwitch() {
  const play = useContext(ModeContext);
  if (!play) throw new Error("useModeSwitch needs ModeTransitionProvider");
  return play;
}

// Full-screen change between faculty and student modes, built from the logo:
// a dawn sky blooms out of the button that was pressed, the violet hill rises
// over it with the new mode's name, and then everything folds back into the
// wordmark's disc in the top-left corner, revealing the new home screen.
export function ModeTransitionProvider({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const [role, setRole] = useState<Role>("faculty");
  const busy = useRef(false);

  const play = useCallback<Play>((next, origin, swap) => {
    const el = root.current;
    if (!el || busy.current) return;
    busy.current = true;
    setRole(next);

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const at = `${origin.x}px ${origin.y}px`;
    // The wordmark's disc sits about here in every shell layout.
    const logo = document.querySelector("[data-logo-disc]")?.getBoundingClientRect();
    const end = logo ? `${logo.left + logo.width / 2}px ${logo.top + logo.height / 2}px` : "120px 60px";
    const big = Math.hypot(window.innerWidth, window.innerHeight) * 1.1;

    // Wait two frames so the new role's letters are rendered before they are animated.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const q = gsap.utils.selector(el);
      if (reduce) {
        gsap
          .timeline({ onComplete: () => void (busy.current = false) })
          .set(el, { display: "block", clipPath: "none", opacity: 0 })
          .to(el, { opacity: 1, duration: 0.2 })
          .add(swap)
          .to(el, { opacity: 0, duration: 0.3, delay: 0.3 })
          .set(el, { display: "none" });
        return;
      }

      const tl = gsap.timeline({
        defaults: { ease: "power3.inOut" },
        onComplete: () => {
          gsap.set(el, { display: "none" });
          busy.current = false;
        },
      });
      tl.set(el, { display: "block", opacity: 1, clipPath: `circle(0px at ${at})` })
        .set(q(".mt-hill"), { yPercent: 100 })
        .set(q(".mt-char"), { yPercent: 110, opacity: 0 })
        .set(q(".mt-line"), { y: 18, opacity: 0 })
        .set(q(".mt-sun"), { scale: 0.4, opacity: 0 })
        .to(el, { clipPath: `circle(${big}px at ${at})`, duration: 0.8 })
        .to(q(".mt-sun"), { scale: 1, opacity: 1, duration: 0.9, ease: "expo.out" }, 0.25)
        .to(q(".mt-hill"), { yPercent: 0, duration: 0.85, ease: "expo.out" }, 0.35)
        .to(q(".mt-char"), { yPercent: 0, opacity: 1, duration: 0.7, stagger: 0.035, ease: "expo.out" }, 0.55)
        .to(q(".mt-line"), { y: 0, opacity: 1, duration: 0.6, ease: "power2.out" }, 0.75)
        .add(swap, 1.35)
        .to(q(".mt-char, .mt-line"), { opacity: 0, y: -16, duration: 0.35, stagger: 0.01, ease: "power2.in" }, 1.6)
        .to(q(".mt-hill"), { yPercent: -18, duration: 0.9, ease: "power2.in" }, 1.6)
        .to(el, { clipPath: `circle(0px at ${end})`, duration: 0.85, ease: "expo.inOut" }, 1.7)
        .add(() => {
          // The new screen's sheet content rises in as the overlay folds away.
          gsap.fromTo(
            ".rnd-enter > *",
            { y: 24, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.7, stagger: 0.06, ease: "power3.out", clearProps: "all" },
          );
        }, 2.05);
    }));
  }, []);

  const copy = COPY[role];

  return (
    <ModeContext.Provider value={play}>
      {children}
      <div
        ref={root}
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[100] hidden overflow-hidden"
        style={{ background: "linear-gradient(180deg,#ffd590 0%,#ffab72 38%,#f4919f 62%,#c597d8 100%)" }}
      >
        <div
          className="mt-sun absolute top-[18%] left-1/2 size-[46vmin] -translate-x-1/2 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(255,240,200,.95), rgba(255,200,130,.5) 45%, transparent 70%)" }}
        />
        <svg className="mt-hill absolute inset-x-0 bottom-0 h-[62%] w-full" viewBox="0 0 1440 600" preserveAspectRatio="none">
          <defs>
            <linearGradient id="mt-hill-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#a68ad9" />
              <stop offset="0.4" stopColor="#6d6fd0" />
              <stop offset="1" stopColor="#2f4aa3" />
            </linearGradient>
          </defs>
          <path d="M0 150 C 280 70, 560 20, 860 30 S 1300 110, 1440 130 V600 H0Z" fill="url(#mt-hill-grad)" />
          <path d="M0 230 C 320 170, 640 150, 960 175 S 1340 230, 1440 220 V600 H0Z" fill="#2b3f96" opacity="0.35" />
        </svg>
        <div className="absolute inset-x-0 bottom-[14%] flex flex-col items-center px-6 text-center text-white">
          <div className="font-sans text-[13px] font-semibold tracking-[3px] uppercase opacity-80">
            <span className="mt-line inline-block">Switching to</span>
          </div>
          <div className="mt-2 overflow-hidden pb-2 font-serif text-[clamp(64px,11vw,168px)] leading-[0.95] tracking-[-3px]">
            {copy.title.split("").map((ch, i) => (
              <span key={`${role}-${i}`} className="mt-char inline-block">
                {ch}
              </span>
            ))}
          </div>
          <div className="mt-line mt-3 max-w-[560px] font-serif text-[clamp(18px,1.8vw,24px)] opacity-90">{copy.line}</div>
        </div>
      </div>
    </ModeContext.Provider>
  );
}
