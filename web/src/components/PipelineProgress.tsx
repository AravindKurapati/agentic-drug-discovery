import { CheckCircle2, Circle, Loader2, AlertTriangle } from "lucide-react";

import { STEP_LABELS, STEP_NAMES } from "@/api/types";
import type { RunSnapshot } from "@/api/types";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

interface Props {
  snapshot: RunSnapshot;
}

type StepState = "pending" | "running" | "done" | "error";

function deriveStepStates(snapshot: RunSnapshot): StepState[] {
  const total = STEP_NAMES.length;
  return STEP_NAMES.map((_, idx) => {
    const stepNum = idx + 1;
    if (snapshot.status === "error" && stepNum === snapshot.current_step) return "error";
    if (stepNum < snapshot.current_step) return "done";
    if (stepNum === snapshot.current_step) {
      if (snapshot.status === "done" && stepNum === total) return "done";
      if (snapshot.status === "running") return "running";
      if (snapshot.status === "done") return "done";
      return "pending";
    }
    if (snapshot.status === "done") return "done";
    return "pending";
  });
}

export function PipelineProgress({ snapshot }: Props) {
  const states = deriveStepStates(snapshot);
  const total = STEP_NAMES.length;
  const pct = Math.round((Math.min(snapshot.current_step, total) / total) * 100);

  return (
    <div className="space-y-3">
      <Progress value={snapshot.status === "done" ? 100 : pct} className="h-1.5" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-2">
        {STEP_NAMES.map((name, idx) => {
          const state = states[idx];
          return (
            <div
              key={name}
              className={cn(
                "rounded-lg border p-3 transition-colors",
                state === "running" && "border-primary/60 bg-primary/5 animate-pulse-step",
                state === "done" && "border-[hsl(var(--success)/0.4)] bg-[hsl(var(--success)/0.06)]",
                state === "error" && "border-destructive/50 bg-destructive/10",
                state === "pending" && "border-border bg-card/40"
              )}
            >
              <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground">
                <span>step {idx + 1}/{total}</span>
                {state === "running" && <Loader2 className="h-3 w-3 animate-spin text-primary" />}
                {state === "done" && (
                  <CheckCircle2 className="h-3 w-3 text-[hsl(var(--success))]" />
                )}
                {state === "error" && <AlertTriangle className="h-3 w-3 text-destructive" />}
                {state === "pending" && <Circle className="h-3 w-3" />}
              </div>
              <div
                className={cn(
                  "text-sm font-medium mt-1",
                  state === "pending" && "text-muted-foreground"
                )}
              >
                {STEP_LABELS[name]}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
