import { GitBranch, ShieldCheck, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  line: string;
}

interface ParsedDecision {
  kind: "A" | "B";
  label: string;
  gloss: string;
  detail: string;
  tone: "ok" | "warn" | "info";
}

function parse(line: string): ParsedDecision {
  // Decision A: PASS | RETRY_n | FINAL  mean_plddt=X contigs=...
  const a = line.match(/DECISION_A:\s+(\S+)\s+mean_plddt=([\d.]+)\s+contigs=(.+)/);
  if (a) {
    const [, status, plddt, contigs] = a;
    if (status === "PASS") {
      return {
        kind: "A",
        label: `Decision A — RFdiffusion ${status}`,
        gloss: `Backbone confidence pLDDT ${plddt} ≥ 70.0 — accepted.`,
        detail: `contigs=${contigs}`,
        tone: "ok",
      };
    }
    if (status.startsWith("RETRY_")) {
      const n = status.split("_")[1];
      return {
        kind: "A",
        label: `Decision A — RFdiffusion retry ${n}`,
        gloss: `pLDDT ${plddt} < 70.0 — widening contigs and retrying.`,
        detail: `contigs=${contigs}`,
        tone: "warn",
      };
    }
    return {
      kind: "A",
      label: `Decision A — RFdiffusion ${status}`,
      gloss: `pLDDT ${plddt} after final retry; proceeding with best available.`,
      detail: `contigs=${contigs}`,
      tone: "warn",
    };
  }
  // Decision B: kept N, discarded M (scoring=...)
  const b = line.match(/DECISION_B:\s+kept\s+(\d+),\s+discarded\s+(\d+)\s+\(scoring=([^)]+)\)/);
  if (b) {
    const [, kept, discarded, method] = b;
    const proxy = method.includes("proxy");
    return {
      kind: "B",
      label: "Decision B — candidate filtering",
      gloss: `Kept ${kept}, discarded ${discarded} via ${proxy ? "MPNN log-prob proxy (AF2-Multimer unavailable)" : "AF2-Multimer + pDockQ"}.`,
      detail: `pDockQ ≥ 0.23 AND pLDDT ≥ 70.0`,
      tone: proxy ? "warn" : "ok",
    };
  }
  return {
    kind: "A",
    label: "Decision",
    gloss: line,
    detail: "",
    tone: "info",
  };
}

export function DecisionCard({ line }: Props) {
  const d = parse(line);
  const Icon = d.kind === "A" ? GitBranch : ShieldCheck;
  return (
    <div
      className={cn(
        "rounded-lg border p-3.5 space-y-1",
        d.tone === "ok" && "border-[hsl(var(--success)/0.35)] bg-[hsl(var(--success)/0.06)]",
        d.tone === "warn" && "border-[hsl(var(--warning)/0.4)] bg-[hsl(var(--warning)/0.06)]",
        d.tone === "info" && "border-border bg-card"
      )}
    >
      <div className="flex items-center gap-1.5 text-xs font-semibold tracking-tight">
        {d.tone === "warn" ? (
          <AlertTriangle className="h-3.5 w-3.5 text-[hsl(var(--warning))]" />
        ) : (
          <Icon
            className={cn(
              "h-3.5 w-3.5",
              d.tone === "ok" && "text-[hsl(var(--success))]",
              d.tone === "info" && "text-primary"
            )}
          />
        )}
        {d.label}
      </div>
      <div className="text-sm text-foreground/90">{d.gloss}</div>
      {d.detail && (
        <div className="text-[11px] font-mono text-muted-foreground truncate">{d.detail}</div>
      )}
    </div>
  );
}
