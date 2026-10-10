import { useState, type ReactNode } from "react";
import { TREE_EDGES, TREE_START_NODES, type TreeNode, type TreeNodeId, type TreeNodeKind } from "../../mock/studio";
import { BuildTag } from "../../components/ui";
import { DocIcon } from "../../components/Icons";

// Fixed card heights so connectors meet the card edges exactly.
const HEIGHT: Record<TreeNodeKind, number> = { start: 58, decision: 88, outcome: 122 };
const KIND_LABEL: Record<TreeNodeKind, string> = { start: "Start node", decision: "Decision node", outcome: "Outcome node" };
const CANVAS = { w: 1010, h: 650 };

// Faculty-authored yes/no tree. Decision points are yes/no only (PRD L-03), so there is no "add option".
export function DecisionTree() {
  const [nodes, setNodes] = useState(TREE_START_NODES);
  const [selected, setSelected] = useState<TreeNodeId>("q1");
  const current = nodes[selected];
  const outcomes = new Set(TREE_EDGES.map(([from]) => from));
  const complete = (Object.keys(nodes) as TreeNodeId[]).every((id) => nodes[id].kind === "outcome" || outcomes.has(id));

  // Keep the other fields of the selected node and replace one text field.
  function patch(key: "title" | "detail", value: string) {
    setNodes((prev) => ({ ...prev, [selected]: { ...prev[selected], [key]: value } }));
  }

  return (
    <section className="overflow-hidden rounded-[14px] border border-line bg-card">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line-3 px-7 py-4">
        <div className="flex flex-wrap items-center gap-4">
          <h2 className="m-0 font-serif text-[clamp(30px,2.6vw,42px)] font-normal tracking-[-1px]">Decision tree</h2>
          <BuildTag kind="sample" feature="L-05" />
        </div>
        <span className={`inline-flex h-12 items-center gap-3 rounded-xl px-5 font-serif text-[19px] ${complete ? "bg-ok-soft" : "bg-warn-pill"}`}>
          <span className={`flex size-8 items-center justify-center rounded-full text-white ${complete ? "bg-ok" : "bg-warn"}`}>{complete ? "✓" : "!"}</span>
          {complete ? "Every path has an outcome" : "A path has no outcome"}
        </span>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_340px] max-lg:grid-cols-1">
        <div className="overflow-auto">
          <div className="relative mx-auto" style={{ width: CANVAS.w, height: CANVAS.h }}>
            <svg width={CANVAS.w} height={CANVAS.h} className="absolute inset-0">
              <defs>
                <marker id="dt-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                  <path d="M0 0L10 5L0 10z" fill="#5b6290" />
                </marker>
              </defs>
              {TREE_EDGES.map(([from, to, label]) => (
                <path key={`${from}-${to}`} d={edgePath(nodes[from], nodes[to], label).d} fill="none" stroke="#5b6290" strokeWidth="1.6" markerEnd="url(#dt-arrow)" />
              ))}
            </svg>
            {TREE_EDGES.map(([from, to, label]) => {
              if (!label) return null;
              const path = edgePath(nodes[from], nodes[to], label);
              const yes = label === "Yes";
              return (
                <span
                  key={`${from}-${to}-label`}
                  className={`absolute inline-flex h-8 -translate-x-1/2 -translate-y-1/2 items-center rounded-full px-3.5 font-sans text-[15px] text-ink ${yes ? "bg-[#d9f0dd]" : "bg-[#fbd9d9]"}`}
                  style={{ left: path.lx, top: path.ly }}
                >
                  {label}
                </span>
              );
            })}
            {(Object.keys(nodes) as TreeNodeId[]).map((id) => (
              <NodeCard key={id} node={nodes[id]} on={id === selected} onClick={() => setSelected(id)} />
            ))}
          </div>
        </div>

        <aside className="flex flex-col border-l border-line-3 max-lg:border-t max-lg:border-l-0">
          <div className="border-b border-line-3 px-6">
            <span className="-mb-px inline-block border-b-2 border-indigo px-2.5 pt-4 pb-3 font-serif text-[18px] text-indigo">Node</span>
          </div>
          <div className="flex flex-col gap-5 px-6 py-5">
            <div className="flex items-center gap-3">
              <NodeGlyph kind={current.kind} size={44} />
              <span className="font-serif text-[22px]">{KIND_LABEL[current.kind]}</span>
            </div>
            <Field label={current.kind === "decision" ? "Question" : "Title"}>
              <input
                value={current.title}
                onChange={(event) => patch("title", event.target.value)}
                className="h-12 rounded-[10px] border border-line-2 bg-card px-4 font-sans text-[16px] text-ink outline-indigo"
              />
            </Field>
            <Field label={current.kind === "decision" ? "Counts as yes when:" : current.kind === "start" ? "Setting:" : "What the student finds:"}>
              <textarea
                value={current.detail}
                rows={3}
                onChange={(event) => patch("detail", event.target.value)}
                className="resize-y rounded-[10px] border border-line-2 bg-card px-4 py-2.5 font-sans text-[16px] leading-snug text-ink outline-indigo"
              />
            </Field>
            {current.kind === "decision" ? (
              <Field label="Options">
                <Option color="#9fd6a8" label="Yes" />
                <Option color="#f4a3a3" label="No" />
                <span className="font-sans text-[13px] text-muted">Decision points are yes or no, judged from what the student said.</span>
              </Field>
            ) : null}
          </div>
        </aside>
      </div>
    </section>
  );
}

function NodeCard({ node, on, onClick }: { node: TreeNode; on: boolean; onClick: () => void }) {
  const look =
    node.kind === "start"
      ? "border-indigo bg-indigo-soft justify-center"
      : node.kind === "decision"
        ? "border-[#f2b77d] bg-[#fffaf4]"
        : "border-indigo-line/70 bg-card items-start";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`absolute flex items-center gap-4 rounded-[10px] border-[1.5px] px-5 text-left shadow-[0_6px_18px_-12px_rgba(25,31,92,.4)] transition-shadow ${look} ${node.kind === "outcome" ? "py-4" : ""}`}
      style={{
        left: node.x,
        top: node.y,
        width: node.w,
        height: HEIGHT[node.kind],
        boxShadow: on ? "0 0 0 4px rgba(74,95,217,.22), 0 6px 18px -12px rgba(25,31,92,.4)" : undefined,
      }}
    >
      {node.kind === "start" ? (
        <>
          <FlagIcon />
          <span className="font-serif text-[21px]">Start</span>
        </>
      ) : (
        <>
          <NodeGlyph kind={node.kind} size={48} />
          <span className="flex min-w-0 flex-col gap-1">
            <span className="font-serif text-[21px] leading-tight tracking-[-0.2px]">{node.title}</span>
            {node.kind === "outcome" ? <span className="font-sans text-[14.5px] leading-snug text-ink">{node.detail}</span> : null}
          </span>
        </>
      )}
    </button>
  );
}

function NodeGlyph({ kind, size }: { kind: TreeNodeKind; size: number }) {
  return (
    <span className="flex shrink-0 items-center justify-center rounded-full bg-indigo-soft text-ink" style={{ width: size, height: size }}>
      {kind === "decision" ? <span className="font-serif text-[30px] leading-none">?</span> : kind === "start" ? <FlagIcon /> : <DocIcon size={size * 0.5} />}
    </span>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-2.5">
      <span className="font-serif text-[18px]">{label}</span>
      {children}
    </label>
  );
}

function Option({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex h-12 items-center gap-3.5 rounded-[10px] border border-line-2 px-4 font-sans text-[16px]">
      <span className="size-4 rounded-full" style={{ background: color }} />
      {label}
    </div>
  );
}

function FlagIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round" strokeLinecap="round" aria-hidden>
      <path d="M5 21V4M5 4h11l-2 4 2 4H5" />
    </svg>
  );
}

// Elbow connector: down from the source, across, then down into the target. "Yes" leaves from the
// left of the card and "No" from the right, as in the faculty mockup.
function edgePath(from: TreeNode, to: TreeNode, label: string) {
  const x1 = from.x + from.w * (label === "Yes" ? 0.2 : label === "No" ? 0.8 : 0.5);
  const y1 = from.y + HEIGHT[from.kind];
  const x2 = to.x + to.w / 2;
  const y2 = to.y - 2;
  if (Math.abs(x1 - x2) < 2) return { d: `M${x1} ${y1} V${y2}`, lx: x1, ly: (y1 + y2) / 2 };
  const ym = y1 + Math.min(42, (y2 - y1) / 2);
  const r = 16;
  const dir = x2 > x1 ? 1 : -1;
  return {
    d: `M${x1} ${y1} V${ym - r} Q${x1} ${ym} ${x1 + dir * r} ${ym} H${x2 - dir * r} Q${x2} ${ym} ${x2} ${ym + r} V${y2}`,
    lx: (x1 + x2) / 2,
    ly: ym,
  };
}
