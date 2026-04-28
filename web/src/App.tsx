import { Navigate, Route, Routes, useParams } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Sparkles,
  XCircle,
} from "lucide-react";

import { Sidebar } from "@/components/Sidebar";
import { RunForm } from "@/components/RunForm";
import { PipelineProgress } from "@/components/PipelineProgress";
import { LogStream } from "@/components/LogStream";
import { DecisionCard } from "@/components/DecisionCard";
import { CandidateTable } from "@/components/CandidateTable";
import { ScatterPlot } from "@/components/ScatterPlot";
import { LiteratureList } from "@/components/LiteratureList";
import { ReportMarkdown } from "@/components/ReportMarkdown";
import { ToolGraph } from "@/components/ToolGraph";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useRunStream } from "@/hooks/useRunStream";
import type { RunStatus } from "@/api/types";
import { cn, formatDateTime, formatDuration } from "@/lib/utils";

export default function App() {
  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <Sidebar />
      <main className="flex-1 min-w-0">
        <Routes>
          <Route path="/" element={<NewRunPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/runs/:jobId" element={<RunDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function PageShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="px-8 py-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && (
          <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
        )}
      </div>
      {children}
    </div>
  );
}

function NewRunPage() {
  return (
    <PageShell
      title="Start a new run"
      subtitle="Pick a target — the agent does the rest."
    >
      <RunForm />
    </PageShell>
  );
}

function AboutPage() {
  return (
    <PageShell
      title="How it works"
      subtitle="A seven-step agentic pipeline over NVIDIA BioNeMo NIMs, with two LLM-driven decision points."
    >
      <div className="grid lg:grid-cols-[1fr_360px] gap-8">
        <div className="space-y-4 text-sm leading-relaxed text-foreground/90">
          <p>
            The agent takes a protein target (UniProt ID or gene name) and
            produces a ranked report of designed binder candidates. Each step
            calls a tool — UniProt, ESMFold, RFdiffusion, ProteinMPNN,
            AlphaFold2-Multimer (when available), and a literature RAG over
            PubMed abstracts.
          </p>
          <p>
            Two LLM-driven decisions appear in the run log. <strong>Decision
            A</strong> handles backbone quality: if RFdiffusion's mean pLDDT is
            below 70, contigs widen and the call is retried up to twice.{" "}
            <strong>Decision B</strong> filters scored candidates against pDockQ
            ≥ 0.23 and pLDDT ≥ 70, falling back to a ProteinMPNN log-prob proxy
            when the AF2-Multimer free-tier endpoint is unavailable.
          </p>
          <p>
            All NIM calls are cached on disk by SHA-256 of the request payload,
            so debug runs cost nothing once the result has been seen. The
            decision log, scored candidates, literature hits, and final
            markdown report are streamed live via Server-Sent Events.
          </p>
        </div>
        <ToolGraph />
      </div>
    </PageShell>
  );
}

function RunDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { snapshot, error } = useRunStream(jobId ?? null);

  if (!jobId) return <Navigate to="/" replace />;

  if (!snapshot) {
    return (
      <PageShell title="Loading run…">
        <Card>
          <CardContent className="py-10 flex items-center justify-center text-sm text-muted-foreground gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Connecting to run stream…
          </CardContent>
        </Card>
      </PageShell>
    );
  }

  const result = snapshot.result;
  const scored = result?.scored ?? [];
  const literature = result?.literature ?? [];
  const decisions = snapshot.decisions;

  return (
    <PageShell
      title={`${snapshot.target} — run ${snapshot.job_id}`}
      subtitle={`${snapshot.max_candidates} max candidates · ${
        snapshot.use_af2_multimer ? "AF2-Multimer enabled" : "proxy scoring"
      }${snapshot.dry_run ? " · dry run" : ""}`}
    >
      <RunHeader
        status={snapshot.status}
        startedAt={snapshot.started_at}
        finishedAt={snapshot.finished_at}
        keptCount={result?.kept_count ?? null}
        evaluated={result?.candidates_evaluated ?? null}
        error={snapshot.error ?? error}
      />

      <div className="mt-6">
        <PipelineProgress snapshot={snapshot} />
      </div>

      <Tabs defaultValue="live" className="mt-6">
        <TabsList>
          <TabsTrigger value="live">Live</TabsTrigger>
          <TabsTrigger value="candidates" disabled={scored.length === 0}>
            Candidates {scored.length > 0 && `(${scored.length})`}
          </TabsTrigger>
          <TabsTrigger value="literature" disabled={!result}>
            Literature {literature.length > 0 && `(${literature.length})`}
          </TabsTrigger>
          <TabsTrigger value="report" disabled={!result?.report_md}>
            Report
          </TabsTrigger>
        </TabsList>

        <TabsContent value="live" className="space-y-4 mt-4">
          <div className="grid lg:grid-cols-[1fr_360px] gap-4">
            <LogStream lines={snapshot.log_lines} />
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">
                  Decisions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {decisions.length === 0 && (
                  <div className="text-xs text-muted-foreground">
                    No decisions logged yet.
                  </div>
                )}
                {decisions.map((line, i) => (
                  <DecisionCard key={i} line={line} />
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="candidates" className="space-y-4 mt-4">
          {scored.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">
                  pDockQ vs interface pLDDT
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScatterPlot candidates={scored} />
                <div className="text-[11px] text-muted-foreground mt-2">
                  Dashed lines mark thresholds (pDockQ ≥ 0.23, pLDDT ≥ 70).
                  Green = kept, amber = discarded.
                </div>
              </CardContent>
            </Card>
          )}
          <CandidateTable candidates={scored} />
        </TabsContent>

        <TabsContent value="literature" className="mt-4">
          <LiteratureList hits={literature} />
        </TabsContent>

        <TabsContent value="report" className="mt-4">
          {result?.report_md ? (
            <ReportMarkdown
              jobId={snapshot.job_id}
              target={snapshot.target}
              markdown={result.report_md}
            />
          ) : (
            <Card>
              <CardContent className="py-8 text-sm text-muted-foreground text-center">
                Report will appear here once the run finishes.
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}

function RunHeader({
  status,
  startedAt,
  finishedAt,
  keptCount,
  evaluated,
  error,
}: {
  status: RunStatus;
  startedAt: string;
  finishedAt: string | null;
  keptCount: number | null;
  evaluated: number | null;
  error: string | null;
}) {
  return (
    <Card>
      <CardContent className="py-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <div className="flex items-center gap-2">
          <StatusBadge status={status} />
        </div>
        <Stat
          icon={<Clock className="h-3.5 w-3.5" />}
          label="Started"
          value={formatDateTime(startedAt)}
        />
        <Stat
          icon={<Sparkles className="h-3.5 w-3.5" />}
          label="Duration"
          value={formatDuration(startedAt, finishedAt)}
        />
        {evaluated !== null && (
          <Stat label="Evaluated" value={String(evaluated)} />
        )}
        {keptCount !== null && (
          <Stat label="Kept" value={String(keptCount)} highlight />
        )}
        {error && (
          <div className="ml-auto rounded-md border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-xs text-destructive max-w-md truncate">
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({
  icon,
  label,
  value,
  highlight,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5">
      {icon && <span className="text-muted-foreground">{icon}</span>}
      <span className="text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          "font-mono text-sm",
          highlight && "text-[hsl(var(--success))] font-semibold"
        )}
      >
        {value}
      </span>
    </div>
  );
}

function StatusBadge({ status }: { status: RunStatus }) {
  if (status === "running") {
    return (
      <Badge className="gap-1.5">
        <Loader2 className="h-3 w-3 animate-spin" /> Running
      </Badge>
    );
  }
  if (status === "done") {
    return (
      <Badge variant="success" className="gap-1.5">
        <CheckCircle2 className="h-3 w-3" /> Done
      </Badge>
    );
  }
  if (status === "error") {
    return (
      <Badge variant="destructive" className="gap-1.5">
        <XCircle className="h-3 w-3" /> Error
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="gap-1.5">
      <AlertTriangle className="h-3 w-3" /> Queued
    </Badge>
  );
}
