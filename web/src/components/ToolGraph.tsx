import {
  Database,
  Atom,
  Sparkles,
  Dna,
  ShieldCheck,
  BookOpen,
  FileText,
  GitBranch,
} from "lucide-react";

import { Card } from "@/components/ui/card";

const TOOLS = [
  {
    id: "fetch_sequence",
    label: "fetch_sequence",
    desc: "UniProt REST",
    icon: Database,
  },
  {
    id: "run_alphafold2",
    label: "run_alphafold2",
    desc: "ESMFold NIM",
    icon: Atom,
  },
  {
    id: "run_rfdiffusion",
    label: "run_rfdiffusion",
    desc: "RFdiffusion NIM",
    icon: Sparkles,
    decision: "A",
  },
  {
    id: "run_proteinmpnn",
    label: "run_proteinmpnn",
    desc: "ProteinMPNN NIM",
    icon: Dna,
  },
  {
    id: "run_af2_multimer_batch",
    label: "score_complexes",
    desc: "AF2-Multimer + Modal",
    icon: ShieldCheck,
    decision: "B",
  },
  {
    id: "query_literature",
    label: "query_literature",
    desc: "Chroma RAG · PubMed",
    icon: BookOpen,
  },
  {
    id: "generate_report",
    label: "generate_report",
    desc: "Markdown synthesis",
    icon: FileText,
  },
];

export function ToolGraph() {
  return (
    <div className="space-y-3">
      {TOOLS.map((t, idx) => (
        <div key={t.id} className="flex items-stretch gap-3">
          <div className="flex flex-col items-center">
            <div className="h-9 w-9 rounded-full bg-primary/15 grid place-items-center text-primary">
              <t.icon className="h-4 w-4" />
            </div>
            {idx < TOOLS.length - 1 && (
              <div className="w-px flex-1 bg-border my-1" />
            )}
          </div>
          <Card className="flex-1 p-3.5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="font-mono text-sm font-semibold">{t.label}</div>
                <div className="text-xs text-muted-foreground">{t.desc}</div>
              </div>
              {t.decision && (
                <div className="flex items-center gap-1.5 rounded-md bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                  <GitBranch className="h-3 w-3" />
                  Decision {t.decision}
                </div>
              )}
            </div>
          </Card>
        </div>
      ))}
    </div>
  );
}
