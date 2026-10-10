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

// Watercolor wash drawn by a fragment shader at the screen's full pixel density. The reveal is a
// circle whose edge is pushed around by noise, with a darker pigment rim, so it reads as paint
// bleeding across paper rather than a vector shape. Everything is in device pixels.
const FRAGMENT = `
precision highp float;
uniform vec2 uRes;
uniform vec2 uCenter;
uniform float uRadius;
uniform float uTime;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 frag = gl_FragCoord.xy;
  float s = uRes.y / 1000.0;
  vec2 uv = frag / uRes.y;
  float t = uTime;

  vec2 q = vec2(fbm(uv * 1.6 + vec2(0.0, t * 0.05)), fbm(uv * 1.6 + vec2(5.2, 1.3) - t * 0.04));
  float f = fbm(uv * 2.0 + q * 1.8);
  float k = clamp(frag.y / uRes.y + (f - 0.5) * 0.5, 0.0, 1.0);

  vec3 indigo = vec3(0.29, 0.35, 0.80);
  vec3 lilac = vec3(0.68, 0.60, 0.90);
  vec3 rose = vec3(0.97, 0.64, 0.67);
  vec3 apricot = vec3(1.0, 0.77, 0.52);
  vec3 cream = vec3(1.0, 0.93, 0.81);
  vec3 col = mix(indigo, lilac, smoothstep(0.0, 0.32, k));
  col = mix(col, rose, smoothstep(0.32, 0.56, k));
  col = mix(col, apricot, smoothstep(0.56, 0.78, k));
  col = mix(col, cream, smoothstep(0.78, 1.0, k));

  // Pigment pooling and paper grain.
  float pool = fbm(uv * 6.0 + q * 3.0);
  col *= 1.0 - 0.12 * smoothstep(0.5, 0.8, pool);
  col += (noise(frag * 0.9) * 0.5 + noise(frag * 0.33) * 0.5 - 0.5) * 0.04;

  // A pale wash in the middle keeps the navy title readable.
  vec2 cc = (frag - uRes * 0.5) / uRes.y * vec2(0.85, 1.7);
  col = mix(col, vec3(1.0, 0.975, 0.94), 0.62 * exp(-dot(cc, cc) * 4.5));

  float d = length(frag - uCenter);
  float amp = mix(3.0, 80.0, clamp(uRadius / (900.0 * s), 0.0, 1.0)) * s;
  float edge = d + (fbm(uv * 3.2 + vec2(t * 0.12, 0.0)) - 0.5) * 2.0 * amp;
  float feather = 14.0 * s;
  float a = (1.0 - smoothstep(uRadius - feather, uRadius, edge)) * step(0.5, uRadius);
  float rim = smoothstep(feather * 3.0, 0.0, abs(edge - uRadius + feather)) ;
  col = mix(col, col * vec3(0.76, 0.72, 0.9), rim * 0.55);

  gl_FragColor = vec4(col * a, a);
}`;

const VERTEX = `attribute vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;

type Wash = {
  gl: WebGLRenderingContext;
  uni: Record<"uRes" | "uCenter" | "uRadius" | "uTime", WebGLUniformLocation | null>;
};

function createWash(canvas: HTMLCanvasElement): Wash | null {
  const gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: false });
  if (!gl) return null;
  const compile = (type: number, src: string) => {
    const shader = gl.createShader(type)!;
    gl.shaderSource(shader, src);
    gl.compileShader(shader);
    return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
  };
  const vs = compile(gl.VERTEX_SHADER, VERTEX);
  const fs = compile(gl.FRAGMENT_SHADER, FRAGMENT);
  if (!vs || !fs) return null;
  const program = gl.createProgram()!;
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(program, "p");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  return {
    gl,
    uni: {
      uRes: gl.getUniformLocation(program, "uRes"),
      uCenter: gl.getUniformLocation(program, "uCenter"),
      uRadius: gl.getUniformLocation(program, "uRadius"),
      uTime: gl.getUniformLocation(program, "uTime"),
    },
  };
}

// Full-screen change between faculty and student modes: a watercolor wash bleeds out of the
// button that was pressed, the new mode's name rises in, and the wash draws back into the
// wordmark's disc in the top-left corner, revealing the new home screen.
export function ModeTransitionProvider({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const wash = useRef<Wash | null>(null);
  const [role, setRole] = useState<Role>("faculty");
  const busy = useRef(false);

  const play = useCallback<Play>((next, origin, swap) => {
    const el = root.current;
    const cv = canvas.current;
    if (!el || !cv || busy.current) return;
    busy.current = true;
    setRole(next);

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduce && !wash.current) wash.current = createWash(cv);
    const w = wash.current;

    // Wait two frames so the new role's letters are rendered before they are animated.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const q = gsap.utils.selector(el);
      const done = () => {
        gsap.set(el, { display: "none" });
        busy.current = false;
      };

      if (reduce || !w) {
        gsap
          .timeline({ onComplete: done })
          .set(el, { display: "block", opacity: 0 })
          .set(q(".mt-fallback"), { display: "block" })
          .set(q(".mt-char, .mt-line"), { opacity: 1, y: 0, yPercent: 0, filter: "none" })
          .to(el, { opacity: 1, duration: 0.25 })
          .add(swap)
          .to(el, { opacity: 0, duration: 0.35, delay: 0.5 });
        return;
      }

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const W = Math.round(window.innerWidth * dpr);
      const H = Math.round(window.innerHeight * dpr);
      cv.width = W;
      cv.height = H;
      w.gl.viewport(0, 0, W, H);

      // GL's y axis points up, so screen coordinates are flipped once here.
      const logo = document.querySelector("[data-logo-disc]")?.getBoundingClientRect();
      const end = logo ? { x: logo.left + logo.width / 2, y: logo.top + logo.height / 2 } : { x: 120, y: 60 };
      const state = { r: 0, x: origin.x * dpr, y: H - origin.y * dpr, time: Math.random() * 50 };
      const cover = Math.hypot(Math.max(state.x, W - state.x), Math.max(state.y, H - state.y)) + 200 * dpr;

      let last = performance.now();
      const render = () => {
        const now = performance.now();
        state.time += (now - last) / 1000;
        last = now;
        const { gl, uni } = w;
        gl.uniform2f(uni.uRes, W, H);
        gl.uniform2f(uni.uCenter, state.x, state.y);
        gl.uniform1f(uni.uRadius, state.r);
        gl.uniform1f(uni.uTime, state.time);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      };
      render();
      gsap.ticker.add(render);

      gsap
        .timeline({
          onComplete: () => {
            gsap.ticker.remove(render);
            done();
          },
        })
        .set(el, { display: "block", opacity: 1 })
        .set(q(".mt-fallback"), { display: "none" })
        .set(q(".mt-label"), { opacity: 0, y: 10 })
        .set(q(".mt-char"), { opacity: 0, yPercent: 60, filter: "blur(10px)" })
        .set(q(".mt-line"), { opacity: 0, y: 14 })
        .to(state, { r: cover, duration: 0.9, ease: "power2.inOut" }, 0)
        .to(q(".mt-label"), { opacity: 0.75, y: 0, duration: 0.5, ease: "power2.out" }, 0.55)
        .to(q(".mt-char"), { opacity: 1, yPercent: 0, filter: "blur(0px)", duration: 0.75, stagger: 0.04, ease: "expo.out" }, 0.6)
        .to(q(".mt-line"), { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 0.8)
        .add(swap, 1.2)
        .to(q(".mt-label, .mt-char, .mt-line"), { opacity: 0, y: -12, duration: 0.35, stagger: 0.012, ease: "power2.in" }, 1.45)
        .to(state, { r: 0, x: end.x * dpr, y: H - end.y * dpr, duration: 0.85, ease: "power3.inOut" }, 1.6)
        .add(() => {
          // The new screen's content rises in as the wash draws back into the logo.
          gsap.fromTo(
            ".rnd-enter > *",
            { y: 20, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.7, stagger: 0.06, ease: "power3.out", clearProps: "all" },
          );
        }, 1.85);
    }));
  }, []);

  const copy = COPY[role];

  return (
    <ModeContext.Provider value={play}>
      {children}
      <div ref={root} aria-hidden className="pointer-events-none fixed inset-0 z-[100] hidden">
        <div
          className="mt-fallback absolute inset-0 hidden"
          style={{ background: "linear-gradient(180deg,#ffedcf 0%,#ffc58a 35%,#f6a3aa 62%,#ad9ae5 100%)" }}
        />
        <canvas ref={canvas} className="absolute inset-0 h-full w-full" />
        <div className="absolute inset-0 flex flex-col items-center justify-center px-6 text-center text-[#141a55]">
          <div className="mt-label font-sans text-[13px] font-semibold tracking-[4px] uppercase">Switching to</div>
          <div className="mt-3 pb-2 font-serif text-[clamp(72px,11vw,176px)] leading-[0.95] tracking-[-0.03em]">
            {copy.title.split("").map((ch, i) => (
              <span key={`${role}-${i}`} className="mt-char inline-block will-change-transform">
                {ch}
              </span>
            ))}
          </div>
          <div className="mt-line mt-4 max-w-[600px] font-serif text-[clamp(19px,1.8vw,25px)] text-[#2a3175]">{copy.line}</div>
        </div>
      </div>
    </ModeContext.Provider>
  );
}
