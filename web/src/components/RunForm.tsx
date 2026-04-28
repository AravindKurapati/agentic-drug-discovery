import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Beaker } from "lucide-react";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import type { StartRunRequest } from "@/api/types";

const SUGGESTED = ["EGFR", "PCSK9", "P00533"];

export function RunForm() {
  const [target, setTarget] = useState("EGFR");
  const [maxCandidates, setMaxCandidates] = useState(5);
  const [useAf2Multimer, setUseAf2Multimer] = useState(false);
  const [dryRun, setDryRun] = useState(false);

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (req: StartRunRequest) => api.startRun(req),
    onSuccess: ({ job_id }) => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      navigate(`/runs/${job_id}`);
    },
  });

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <div className="flex items-center gap-2 text-primary">
          <Beaker className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wider">New run</span>
        </div>
        <CardTitle className="text-2xl">Design a protein binder</CardTitle>
        <CardDescription>
          The agent will fetch the target sequence, predict its structure, generate binder
          backbones, design sequences, score complexes, retrieve relevant literature, and
          produce a ranked report.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="target">
            Target protein
          </label>
          <Input
            id="target"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="UniProt ID or gene name"
            className="font-mono"
          />
          <div className="flex items-center gap-1.5 pt-1">
            <span className="text-xs text-muted-foreground mr-1">Try:</span>
            {SUGGESTED.map((s) => (
              <button
                type="button"
                key={s}
                onClick={() => setTarget(s)}
                className="text-xs font-mono rounded-md border border-border bg-secondary/50 px-2 py-0.5 hover:bg-accent transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-baseline justify-between">
            <label className="text-sm font-medium">Max candidates</label>
            <span className="text-sm font-mono text-primary">{maxCandidates}</span>
          </div>
          <Slider
            min={1}
            max={10}
            step={1}
            value={[maxCandidates]}
            onValueChange={([v]) => setMaxCandidates(v)}
          />
          <div className="text-xs text-muted-foreground">
            Number of binder backbones taken forward to sequence design and scoring.
          </div>
        </div>

        <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-secondary/30 p-3">
          <div>
            <div className="text-sm font-medium">Enable AF2-Multimer scoring</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              Currently unavailable on the NVIDIA free tier (504s). Off = proxy scoring via
              ProteinMPNN log-probability.
            </div>
          </div>
          <Switch checked={useAf2Multimer} onCheckedChange={setUseAf2Multimer} />
        </div>

        <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-secondary/30 p-3">
          <div>
            <div className="text-sm font-medium">Dry run (cache only)</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              Skip live NIM calls. Useful for testing the UI without spending API credits.
            </div>
          </div>
          <Switch checked={dryRun} onCheckedChange={setDryRun} />
        </div>

        {mutation.isError && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {(mutation.error as Error).message}
          </div>
        )}

        <Button
          size="lg"
          className="w-full"
          disabled={!target.trim() || mutation.isPending}
          onClick={() =>
            mutation.mutate({
              target: target.trim(),
              max_candidates: maxCandidates,
              use_af2_multimer: useAf2Multimer,
              dry_run: dryRun,
            })
          }
        >
          {mutation.isPending ? "Starting…" : "Run pipeline"}
          {!mutation.isPending && <ArrowRight className="h-4 w-4" />}
        </Button>
      </CardContent>
    </Card>
  );
}
