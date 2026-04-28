import { useEffect, useRef } from "react";

// 3Dmol attaches to window and pulls in a global. We let the bundler include it
// but use the CDN-style global for simplicity (the npm package exposes the same API).
declare global {
  interface Window {
    $3Dmol: any;
  }
}

interface Props {
  pdb: string;
  height?: number;
  className?: string;
}

let scriptPromise: Promise<void> | null = null;

function load3Dmol(): Promise<void> {
  if (typeof window !== "undefined" && window.$3Dmol) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://3Dmol.csb.pitt.edu/build/3Dmol-min.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Failed to load 3Dmol.js"));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

export function StructureViewer({ pdb, height = 360, className }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!pdb || !ref.current) return;
    let viewer: any;
    let cancelled = false;

    load3Dmol()
      .then(() => {
        if (cancelled || !ref.current) return;
        ref.current.innerHTML = "";
        viewer = window.$3Dmol.createViewer(ref.current, {
          backgroundColor: "transparent",
        });
        viewer.addModel(pdb, "pdb");
        viewer.setStyle({}, { cartoon: { color: "spectrum" } });
        viewer.zoomTo();
        viewer.render();
      })
      .catch((err) => {
        if (ref.current) {
          ref.current.innerText = `Failed to render structure: ${(err as Error).message}`;
        }
      });

    return () => {
      cancelled = true;
      if (viewer) viewer.removeAllModels?.();
    };
  }, [pdb]);

  if (!pdb) {
    return (
      <div
        className={className}
        style={{ height }}
        aria-label="No structure available"
      >
        <div className="h-full grid place-items-center rounded-lg border border-dashed border-border text-xs text-muted-foreground">
          No structure for this candidate (proxy-scored).
        </div>
      </div>
    );
  }

  return (
    <div
      ref={ref}
      className={className}
      style={{ height, position: "relative" }}
      aria-label="3D protein structure"
    />
  );
}
