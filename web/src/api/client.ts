import type {
  RunListItem,
  RunSnapshot,
  StartRunRequest,
  StartRunResponse,
} from "./types";

const API_BASE = "/api";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => http<{ ok: boolean }>("/health"),
  listRuns: () => http<RunListItem[]>("/runs"),
  startRun: (body: StartRunRequest) =>
    http<StartRunResponse>("/runs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getRun: (jobId: string) => http<RunSnapshot>(`/runs/${jobId}`),
  reportUrl: (jobId: string) => `${API_BASE}/runs/${jobId}/report.md`,
  streamUrl: (jobId: string) => `${API_BASE}/runs/${jobId}/stream`,
};
