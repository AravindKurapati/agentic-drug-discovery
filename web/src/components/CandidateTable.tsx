import { useState } from "react";
import { ArrowUpDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StructureViewer } from "@/components/StructureViewer";
import type { ScoredCandidate } from "@/api/types";
import { cn } from "@/lib/utils";

interface Props {
  candidates: ScoredCandidate[];
}

type SortKey = "pdockq" | "plddt" | "contacts";
type SortDir = "asc" | "desc";

export function CandidateTable({ candidates }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("pdockq");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const sorted = [...candidates].sort((a, b) => {
    const av = sortValue(a, sortKey);
    const bv = sortValue(b, sortKey);
    return sortDir === "desc" ? bv - av : av - bv;
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-secondary/40 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Candidate</th>
              <th className="text-left px-4 py-2 font-medium">Status</th>
              <SortableTh
                onClick={() => toggleSort("pdockq")}
                active={sortKey === "pdockq"}
                dir={sortDir}
                label="pDockQ"
              />
              <SortableTh
                onClick={() => toggleSort("plddt")}
                active={sortKey === "plddt"}
                dir={sortDir}
                label="pLDDT"
              />
              <SortableTh
                onClick={() => toggleSort("contacts")}
                active={sortKey === "contacts"}
                dir={sortDir}
                label="Contacts"
              />
              <th className="text-left px-4 py-2 font-medium">Note</th>
              <th className="text-right px-4 py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((c) => (
              <>
                <tr
                  key={c.candidate_id}
                  className={cn(
                    "border-t border-border transition-colors hover:bg-accent/30",
                    !c.kept && "opacity-70"
                  )}
                >
                  <td className="px-4 py-2.5 font-mono">{c.candidate_id}</td>
                  <td className="px-4 py-2.5">
                    {c.kept ? (
                      <Badge variant="success">kept</Badge>
                    ) : (
                      <Badge variant="warning">discarded</Badge>
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-mono">
                    <span
                      className={cn(c.pdockq >= 0.23 && "text-[hsl(var(--success))] font-semibold")}
                    >
                      {c.pdockq.toFixed(3)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono">{c.mean_interface_plddt.toFixed(1)}</td>
                  <td className="px-4 py-2.5 font-mono">{c.n_interface_contacts}</td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[14rem] truncate">
                    {c.scoring_note ?? c.discard_reason ?? "—"}
                  </td>
                  <td className="px-2 py-1.5 text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setExpandedId((id) => (id === c.candidate_id ? null : c.candidate_id))
                      }
                    >
                      {expandedId === c.candidate_id ? "Hide" : "View"}
                    </Button>
                  </td>
                </tr>
                {expandedId === c.candidate_id && (
                  <tr className="border-t border-border bg-secondary/20">
                    <td colSpan={7} className="px-4 py-3">
                      <div className="grid lg:grid-cols-2 gap-4">
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                            Binder sequence
                          </div>
                          <div className="font-mono text-[11px] bg-secondary/60 rounded-md p-2 break-all leading-relaxed">
                            {c.binder_sequence ?? "(unavailable)"}
                          </div>
                        </div>
                        <StructureViewer pdb={c.pdb} height={280} />
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-sm text-muted-foreground">
                  No candidates produced.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function sortValue(c: ScoredCandidate, key: SortKey): number {
  if (key === "pdockq") return c.pdockq;
  if (key === "plddt") return c.mean_interface_plddt;
  return c.n_interface_contacts;
}

function SortableTh({
  onClick,
  active,
  dir,
  label,
}: {
  onClick: () => void;
  active: boolean;
  dir: SortDir;
  label: string;
}) {
  return (
    <th className="text-left px-4 py-2 font-medium">
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1 hover:text-foreground transition-colors",
          active && "text-foreground"
        )}
      >
        {label}
        <ArrowUpDown className={cn("h-3 w-3", active ? "opacity-100" : "opacity-40")} />
        {active && <span className="text-[10px]">{dir}</span>}
      </button>
    </th>
  );
}
