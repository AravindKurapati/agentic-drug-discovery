import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StructureViewer } from "@/components/StructureViewer";
import type { ScoredCandidate } from "@/api/types";
import { cn } from "@/lib/utils";

interface Props {
  candidate: ScoredCandidate;
  rank: number;
}

export function CandidateCard({ candidate, rank }: Props) {
  const [expanded, setExpanded] = useState(false);
  const passed = candidate.kept;

  return (
    <Card className={cn("p-4", !passed && "opacity-70")}>
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-muted-foreground">Rank #{rank}</span>
            <span className="font-mono text-sm font-medium">{candidate.candidate_id}</span>
            {passed ? (
              <Badge variant="success">kept</Badge>
            ) : (
              <Badge variant="warning">discarded</Badge>
            )}
          </div>
          {candidate.scoring_note && (
            <div className="text-[11px] text-muted-foreground italic">{candidate.scoring_note}</div>
          )}
          {candidate.discard_reason && (
            <div className="text-[11px] text-[hsl(var(--warning))]">
              {candidate.discard_reason}
            </div>
          )}
        </div>
        <div className="grid grid-cols-3 gap-3 text-right">
          <Metric label="pDockQ" value={candidate.pdockq.toFixed(3)} highlight={passed} />
          <Metric label="pLDDT" value={candidate.mean_interface_plddt.toFixed(1)} />
          <Metric label="Contacts" value={String(candidate.n_interface_contacts)} />
        </div>
      </div>

      {candidate.binder_sequence && (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
            Binder sequence ({candidate.binder_sequence.length} aa)
          </div>
          <div className="font-mono text-[11px] bg-secondary/40 rounded-md p-2 break-all leading-relaxed">
            {candidate.binder_sequence}
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => setExpanded((x) => !x)}>
          {expanded ? "Hide structure" : "View 3D structure"}
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </Button>
      </div>

      {expanded && (
        <div className="mt-2">
          <StructureViewer pdb={candidate.pdb} height={320} />
        </div>
      )}
    </Card>
  );
}

function Metric({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div
        className={cn(
          "font-mono text-base font-semibold",
          highlight && "text-[hsl(var(--success))]"
        )}
      >
        {value}
      </div>
    </div>
  );
}
