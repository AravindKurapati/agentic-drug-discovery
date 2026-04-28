import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ScoredCandidate } from "@/api/types";

interface Props {
  candidates: ScoredCandidate[];
}

export function ScatterPlot({ candidates }: Props) {
  const data = candidates.map((c) => ({
    x: c.mean_interface_plddt,
    y: c.pdockq,
    name: c.candidate_id,
    kept: c.kept,
  }));
  const kept = data.filter((d) => d.kept);
  const discarded = data.filter((d) => !d.kept);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 28, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            type="number"
            dataKey="x"
            name="pLDDT"
            domain={[40, 100]}
            stroke="hsl(var(--muted-foreground))"
            fontSize={11}
            label={{
              value: "Mean interface pLDDT",
              position: "insideBottom",
              offset: -16,
              fill: "hsl(var(--muted-foreground))",
              fontSize: 11,
            }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="pDockQ"
            domain={[0, 1]}
            stroke="hsl(var(--muted-foreground))"
            fontSize={11}
            label={{
              value: "pDockQ",
              angle: -90,
              position: "insideLeft",
              fill: "hsl(var(--muted-foreground))",
              fontSize: 11,
            }}
          />
          <ReferenceLine y={0.23} stroke="hsl(var(--warning))" strokeDasharray="3 3" />
          <ReferenceLine x={70} stroke="hsl(var(--warning))" strokeDasharray="3 3" />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(v: number) => v.toFixed(3)}
            labelFormatter={() => ""}
          />
          <Scatter data={kept} fill="hsl(var(--success))" />
          <Scatter data={discarded} fill="hsl(var(--warning))" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
