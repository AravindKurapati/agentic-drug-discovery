import { ExternalLink, BookOpen } from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card } from "@/components/ui/card";
import type { LiteratureHit } from "@/api/types";

interface Props {
  hits: LiteratureHit[];
}

export function LiteratureList({ hits }: Props) {
  if (hits.length === 0) {
    return (
      <Card className="p-6 text-sm text-muted-foreground flex items-center gap-3">
        <BookOpen className="h-4 w-4" />
        No literature retrieved. Run{" "}
        <code className="font-mono text-xs bg-secondary px-1.5 py-0.5 rounded">
          rag/ingest.py --target {`<target>`}
        </code>{" "}
        first to populate the Chroma index.
      </Card>
    );
  }

  return (
    <Card>
      <Accordion type="single" collapsible className="px-5">
        {hits.map((h, i) => (
          <AccordionItem key={`${h.pmid}-${i}`} value={`${h.pmid}-${i}`}>
            <AccordionTrigger>
              <div className="flex items-start gap-2 text-left">
                <span className="font-mono text-[11px] text-primary mt-0.5 shrink-0">
                  PMID {h.pmid}
                </span>
                <span className="font-medium text-foreground">{h.title}</span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <p className="leading-relaxed text-foreground/90 mb-2">{h.abstract}</p>
              <a
                href={`https://pubmed.ncbi.nlm.nih.gov/${h.pmid}/`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                Open on PubMed <ExternalLink className="h-3 w-3" />
              </a>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </Card>
  );
}
