import { useEffect, useReducer, useRef } from "react";
import { api } from "@/api/client";
import type { RunSnapshot } from "@/api/types";

type State = {
  snapshot: RunSnapshot | null;
  connected: boolean;
  error: string | null;
};

type Action =
  | { type: "snapshot"; snapshot: RunSnapshot }
  | { type: "log"; line: string; current_step: number }
  | { type: "decision"; line: string }
  | { type: "status"; status: RunSnapshot["status"] }
  | { type: "done"; finalSnapshot?: RunSnapshot }
  | { type: "error"; error: string }
  | { type: "connected"; connected: boolean };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "snapshot":
      return { ...state, snapshot: action.snapshot };
    case "log":
      if (!state.snapshot) return state;
      return {
        ...state,
        snapshot: {
          ...state.snapshot,
          log_lines: [...state.snapshot.log_lines, action.line],
          current_step: action.current_step,
        },
      };
    case "decision":
      if (!state.snapshot) return state;
      return {
        ...state,
        snapshot: {
          ...state.snapshot,
          decisions: [...state.snapshot.decisions, action.line],
        },
      };
    case "status":
      if (!state.snapshot) return state;
      return { ...state, snapshot: { ...state.snapshot, status: action.status } };
    case "done":
      if (!state.snapshot) return state;
      return { ...state, snapshot: { ...state.snapshot, status: "done" } };
    case "error":
      return { ...state, error: action.error };
    case "connected":
      return { ...state, connected: action.connected };
    default:
      return state;
  }
}

export function useRunStream(jobId: string | null) {
  const [state, dispatch] = useReducer(reducer, {
    snapshot: null,
    connected: false,
    error: null,
  });
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;
    const url = api.streamUrl(jobId);
    const es = new EventSource(url);
    sourceRef.current = es;

    es.addEventListener("open", () => dispatch({ type: "connected", connected: true }));
    es.addEventListener("snapshot", (ev) => {
      const snap = JSON.parse((ev as MessageEvent).data) as RunSnapshot;
      dispatch({ type: "snapshot", snapshot: snap });
    });
    es.addEventListener("log", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data) as { line: string; current_step: number };
      dispatch({ type: "log", line: d.line, current_step: d.current_step });
    });
    es.addEventListener("decision", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data) as { line: string };
      dispatch({ type: "decision", line: d.line });
    });
    es.addEventListener("status", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data) as { status: RunSnapshot["status"] };
      dispatch({ type: "status", status: d.status });
    });
    es.addEventListener("done", () => {
      dispatch({ type: "done" });
      es.close();
      // refetch full snapshot to pick up the result body
      api.getRun(jobId).then((snap) => dispatch({ type: "snapshot", snapshot: snap })).catch(() => {});
    });
    es.addEventListener("error", (ev) => {
      const data = (ev as MessageEvent).data;
      if (typeof data === "string") {
        try {
          const parsed = JSON.parse(data) as { error?: string };
          if (parsed.error) dispatch({ type: "error", error: parsed.error });
        } catch {
          /* network-level error, EventSource will retry */
        }
      }
    });
    es.addEventListener("ping", () => {});

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, [jobId]);

  return state;
}
