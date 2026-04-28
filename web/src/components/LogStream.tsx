import { useEffect, useRef } from "react";
import { Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  lines: string[];
  className?: string;
  autoScroll?: boolean;
}

function lineClass(line: string): string {
  if (line.includes("WARNING")) return "text-[hsl(var(--warning))]";
  if (line.includes("DECISION_")) return "text-primary font-medium";
  if (line.includes("done")) return "text-[hsl(var(--success))]";
  if (line.includes("starting")) return "text-foreground";
  return "text-muted-foreground";
}

export function LogStream({ lines, className, autoScroll = true }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (autoScroll && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-[hsl(222_47%_4%)] dark:bg-[hsl(222_47%_3%)] overflow-hidden",
        className
      )}
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-secondary/30 text-xs">
        <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-mono text-muted-foreground">run.log</span>
        <span className="ml-auto text-muted-foreground/60 font-mono">{lines.length} lines</span>
      </div>
      <div ref={ref} className="px-4 py-3 font-mono text-xs leading-relaxed h-72 overflow-y-auto">
        {lines.length === 0 && <div className="text-muted-foreground/50">Waiting for output…</div>}
        {lines.map((line, i) => (
          <div key={i} className={cn("whitespace-pre-wrap break-words", lineClass(line))}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
