import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { PlusIcon } from "../../components/Icons";
import { BuildTag, GhostButton, Page, PageHeader, SoftButton } from "../../components/ui";
import { CASE_ROWS } from "../../mock/faculty";

// Faculty case library as cards. A draft opens the decision-tree tab in Studio.
export function CaseLibrary({ go }: { go: Go }) {
  return (
    <Page>
      <PageHeader title="Cases">
        <div className="flex flex-wrap items-center gap-4">
          <BuildTag kind="sample" feature="S-15" />
          <SoftButton size="lg" onClick={() => go("f-studio", { studioTab: "patient" })} className="shadow-[0_10px_24px_-16px_rgba(74,95,217,.7)]">
            <PlusIcon size={20} />
            New case
          </SoftButton>
          <GhostButton onClick={() => go("f-import")} className="h-14 rounded-xl px-7 text-[20px]">
            <UploadIcon />
            Import sample patients
          </GhostButton>
        </div>
      </PageHeader>

      <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(min(100%,400px),1fr))]">
        {CASE_ROWS.map((row) => {
          const draft = row.status === "Draft";
          const open = () => go("f-studio", { studioTab: draft ? "tree" : "patient" });
          return (
            <article
              key={row.name}
              className="flex flex-col rounded-[14px] border border-line bg-card px-6 pt-6 pb-5 shadow-[0_10px_30px_-24px_rgba(25,31,92,.35)] transition-shadow hover:shadow-[0_18px_40px_-24px_rgba(25,31,92,.45)]"
            >
              <div className="flex items-center gap-6 pb-6">
                <Avatar who={row.who} size={128} />
                <div className="min-w-0">
                  <div className="font-serif text-[clamp(24px,2vw,32px)] leading-tight tracking-[-0.5px]">{row.name}</div>
                  <div className="mt-1.5 font-serif text-[19px] text-ink-soft">{row.learner}</div>
                  <div className="mt-2 font-serif text-[18px] text-ink-soft">
                    {row.visits} {row.visits === 1 ? "visit" : "visits"} <span className="px-1.5 text-faint">·</span>
                    <span className={draft ? "text-warn" : ""}>{row.status}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between border-t border-hair-2 pt-4">
                <span className={`inline-flex h-10 items-center rounded-full px-5 font-serif text-[18px] ${draft ? "bg-warn-soft text-warn-deep" : "bg-indigo-soft text-ink"}`}>
                  {draft ? "Branching" : row.tag}
                </span>
                <button type="button" onClick={open} className="font-serif text-[19px] text-indigo underline underline-offset-4 hover:text-ink">
                  Edit
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </Page>
  );
}

function UploadIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 15V3.5M7.5 8L12 3.5 16.5 8M5 12.5V20h14v-7.5" />
    </svg>
  );
}
