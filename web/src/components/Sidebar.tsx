import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Beaker, Info, PlayCircle, Loader2, CheckCircle2, XCircle } from "lucide-react";

import { api } from "@/api/client";
import { cn, formatDateTime } from "@/lib/utils";
import type { RunStatus } from "@/api/types";

function StatusDot({ status }: { status: RunStatus }) {
  if (status === "running")
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />;
  if (status === "done")
    return <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />;
  if (status === "error")
    return <XCircle className="h-3.5 w-3.5 text-destructive" />;
  return <PlayCircle className="h-3.5 w-3.5 text-muted-foreground" />;
}

export function Sidebar() {
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: api.listRuns,
    refetchInterval: 4000,
  });

  return (
    <aside className="w-72 shrink-0 border-r border-border bg-card/30 backdrop-blur-sm flex flex-col h-screen sticky top-0">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-lg bg-primary/15 grid place-items-center">
            <Beaker className="h-5 w-5 text-primary" />
          </div>
          <div>
            <div className="font-semibold leading-tight">Drug Discovery</div>
            <div className="text-xs text-muted-foreground">Agentic binder design</div>
          </div>
        </div>
      </div>

      <nav className="px-3 py-4 space-y-1">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
              isActive
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )
          }
        >
          <PlayCircle className="h-4 w-4" />
          New run
        </NavLink>
        <NavLink
          to="/about"
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
              isActive
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )
          }
        >
          <Info className="h-4 w-4" />
          How it works
        </NavLink>
      </nav>

      <div className="px-5 py-2 text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
        Recent runs
      </div>
      <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-1">
        {runsQuery.data && runsQuery.data.length === 0 && (
          <div className="text-xs text-muted-foreground px-3 py-2">
            No runs yet. Start one from the New run page.
          </div>
        )}
        {runsQuery.data?.map((r) => (
          <NavLink
            key={r.job_id}
            to={`/runs/${r.job_id}`}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors group",
                isActive
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )
            }
          >
            <StatusDot status={r.status} />
            <div className="flex-1 min-w-0">
              <div className="font-medium truncate text-foreground/90">{r.target}</div>
              <div className="text-[11px] text-muted-foreground truncate">
                {formatDateTime(r.started_at)}
                {r.status === "running" && ` · step ${r.current_step}/${r.total_steps}`}
                {r.status === "done" && r.kept_count !== null && ` · ${r.kept_count} kept`}
              </div>
            </div>
          </NavLink>
        ))}
      </div>

      <div className="px-5 py-3 border-t border-border text-[11px] text-muted-foreground">
        NVIDIA BioNeMo NIMs · NeMo Agent Toolkit
      </div>
    </aside>
  );
}
