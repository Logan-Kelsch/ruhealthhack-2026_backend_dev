import { useState } from "react";
import {
  TREE_EDGES,
  TREE_START_NODES,
  type TreeNode,
  type TreeNodeId,
  type TreeNodeKind,
} from "../../mock/studio";

// Approximate card heights so the connector leaves the bottom of the source node.
const HEIGHT: Record<TreeNodeKind, number> = { start: 66, decision: 72, outcome: 100 };

const KIND_COLOR: Record<TreeNodeKind, string> = {
  start: "var(--color-indigo)",
  decision: "var(--color-warn)",
  outcome: "var(--color-ok)",
};
const KIND_LABEL: Record<TreeNodeKind, string> = { start: "Start", decision: "Question", outcome: "Outcome" };

// Faculty-authored yes/no tree. Editing a node updates the card on the canvas.
export function DecisionTree() {
  const [nodes, setNodes] = useState(TREE_START_NODES);
  const [selected, setSelected] = useState<TreeNodeId>("q1");
  const current = nodes[selected];

  // Keep the other fields of the selected node and replace one text field.
  function patch(key: "title" | "detail", value: string) {
    setNodes((prev) => ({
      ...prev,
      [selected]: { ...prev[selected], [key]: value },
    }));
  }

  return (
    <div className="grid min-h-[620px] grid-cols-[minmax(0,1fr)_280px] overflow-hidden rounded-2xl border border-line bg-card">
      <div className="relative overflow-auto bg-canvas bg-[radial-gradient(var(--color-canvas-dot)_1px,transparent_1px)] bg-[length:20px_20px]">
        <div className="relative mx-auto h-[620px] w-[940px]">
          <svg width="940" height="620" className="absolute inset-0 overflow-visible">
            <defs>
              <marker id="dt-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M0 0L10 5L0 10z" fill="var(--color-inactive)" />
              </marker>
            </defs>
            {TREE_EDGES.map(([from, to]) => {
              const path = edgePath(nodes[from], nodes[to]);
              return <path key={`${from}-${to}`} d={path.d} fill="none" stroke="#b6bad6" strokeWidth="1.5" markerEnd="url(#dt-arrow)" />;
            })}
          </svg>
          {TREE_EDGES.map(([from, to, label]) => {
            if (!label) return null;
            const path = edgePath(nodes[from], nodes[to]);
            const yes = label === "Yes";
            return (
              <span
                key={`${from}-${to}-label`}
                className={`absolute inline-flex h-[22px] -translate-x-1/2 -translate-y-1/2 items-center rounded-md px-2 text-xs font-semibold ${yes ? "bg-ok-soft text-ok" : "bg-danger-soft text-danger"}`}
                style={{ left: path.lx, top: path.ly }}
              >
                {label}
              </span>
            );
          })}
          {(Object.keys(nodes) as TreeNodeId[]).map((id) => {
            const node = nodes[id];
            const on = id === selected;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setSelected(id)}
                className="absolute flex flex-col gap-1 rounded-xl border bg-card px-3.5 py-3 text-left hover:border-inactive"
                style={{
                  left: node.x,
                  top: node.y,
                  width: node.w,
                  borderColor: on ? "var(--color-indigo)" : "var(--color-line-3)",
                  boxShadow: on ? "0 0 0 3px rgba(43,58,184,.14)" : "0 1px 2px rgba(20,27,77,.05)",
                }}
              >
                <span className="text-[11px] font-bold tracking-[0.6px] uppercase" style={{ color: KIND_COLOR[node.kind] }}>
                  {KIND_LABEL[node.kind]}
                </span>
                <span className="text-[14.5px] leading-snug font-semibold">{node.title}</span>
                {node.kind === "outcome" ? <span className="text-[12.5px] leading-snug text-ink-soft">{node.detail}</span> : null}
              </button>
            );
          })}
        </div>
      </div>

      <aside className="flex flex-col border-l border-hair-2">
        <div className="border-b border-hair-2 px-[18px] py-4">
          <div className="text-[11px] font-bold tracking-[0.6px] uppercase" style={{ color: KIND_COLOR[current.kind] }}>
            {KIND_LABEL[current.kind]}
          </div>
          <div className="mt-1 text-[15px] font-semibold">Edit node</div>
        </div>
        <div className="flex flex-col gap-3.5 px-[18px] py-4">
          <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink-soft">
            {current.kind === "decision" ? "Question" : "Title"}
            <input
              value={current.title}
              onChange={(event) => patch("title", event.target.value)}
              className="h-[38px] rounded-[9px] border border-line-2 px-3 text-sm font-normal text-ink outline-indigo"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink-soft">
            {current.kind === "decision" ? "Counts as yes when" : current.kind === "start" ? "Setting" : "What the student finds"}
            <textarea
              value={current.detail}
              rows={4}
              onChange={(event) => patch("detail", event.target.value)}
              className="resize-y rounded-[9px] border border-line-2 px-3 py-2.5 text-sm leading-snug font-normal text-ink outline-indigo"
            />
          </label>
          {current.kind === "decision" ? (
            <div className="flex flex-col gap-1.5">
              <span className="text-[12.5px] font-semibold text-ink-soft">Branches</span>
              <BranchRow color="var(--color-ok)" label="Yes" />
              <BranchRow color="var(--color-danger)" label="No" />
              <button type="button" className="h-[34px] rounded-[9px] border border-dashed border-line-4 text-[13px] text-ink-soft">
                Add branch
              </button>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

function BranchRow({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex h-9 items-center gap-2.5 rounded-[9px] border border-line px-3 text-sm">
      <span className="size-2 rounded-full" style={{ background: color }} />
      {label}
    </div>
  );
}

// Cubic curve from the bottom center of one card to the top center of the next.
function edgePath(from: TreeNode, to: TreeNode) {
  const x1 = from.x + from.w / 2;
  const y1 = from.y + HEIGHT[from.kind];
  const x2 = to.x + to.w / 2;
  const y2 = to.y - 3;
  const midY = (y1 + y2) / 2;
  return {
    d: `M${x1} ${y1} C${x1} ${midY},${x2} ${midY},${x2} ${y2}`,
    lx: (x1 + x2) / 2,
    ly: midY,
  };
}
