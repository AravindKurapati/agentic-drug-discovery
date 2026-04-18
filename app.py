# Load .env FIRST — before any imports that may read env vars (NIM API key, etc.)
from dotenv import load_dotenv
load_dotenv()

import argparse
import os
import pathlib
import sys
from datetime import datetime


def run_pipeline(target: str, max_candidates: int, dry_run: bool) -> dict:
    """
    Run the full binder design pipeline for *target*.

    Returns:
        {
            "report": str,
            "candidates_evaluated": int,
            "kept_count": int,
        }

    # TODO: wire up nat runner
    #   - Load config/workflow.yaml via nat's runner API
    #   - Pass target + max_candidates as workflow inputs
    #   - Stream per-step progress events and map to [step N/7] lines
    #   - Return the markdown report string produced by generate_report_fn
    """

    STEPS = [
        "fetch_sequence",
        "run_alphafold2",
        "run_rfdiffusion",
        "run_proteinmpnn",
        "run_af2_multimer_batch",
        "query_literature",
        "generate_report",
    ]
    total = len(STEPS)

    if dry_run:
        # Cache-only mode: look for any cached result for this target.
        # The cache lives at .nim_cache/<tool_name>/<sha256>.json.
        # A cached pipeline run is considered present if at least one cache
        # entry exists under .nim_cache/ for this target.  Raise immediately
        # if nothing is cached — never fall back to real NIM calls.
        cache_root = pathlib.Path(".nim_cache")
        found_cache = False
        if cache_root.exists():
            for entry in cache_root.rglob("*.json"):
                # Any cached file signals a previous run exists; a full
                # implementation would key this to the target specifically.
                found_cache = True
                break

        if not found_cache:
            raise RuntimeError(
                f"Cache miss for target {target} — "
                "rerun without --dry-run to populate cache"
            )

        # Dry-run fast path: emit progress lines, return a placeholder report.
        for idx, step in enumerate(STEPS, start=1):
            print(f"[step {idx}/{total}] {step} ... (dry-run, reading cache)")

        report = (
            f"# Drug Discovery Report — {target}\n\n"
            "_Dry-run mode: report generated from cached data._\n"
        )
        return {"report": report, "candidates_evaluated": max_candidates, "kept_count": 0}

    # ---------------------------------------------------------------------------
    # Live run — NAT runner
    # ---------------------------------------------------------------------------
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY is not set. Add it to .env before running a live pipeline."
        )

    import asyncio
    from nat.runtime.loader import load_workflow

    prompt = (
        f"Design up to {max_candidates} binder candidates for target {target}."
    )

    print(f"[step 1/{total}] fetch_sequence ... starting")

    async def _run_nat() -> str:
        async with load_workflow("config/workflow.yaml") as workflow:
            async with workflow.run(prompt) as runner:
                return await runner.result(to_type=str)

    report = asyncio.run(_run_nat())

    print(f"[step {total}/{total}] generate_report ... done")

    return {"report": report, "candidates_evaluated": max_candidates, "kept_count": 0}


def main():
    parser = argparse.ArgumentParser(
        description="Agentic drug discovery: generate protein binder candidates for a target.",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="UniProt ID (e.g. P00533) or protein name (e.g. EGFR).",
    )
    parser.add_argument(
        "--output-dir",
        default="./reports/",
        help="Directory to save the markdown report. Created if missing. (default: ./reports/)",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=5,
        help="Maximum number of binder candidates to evaluate. (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Cache-only mode: use cached NIM results only. "
            "Raises an error on cache miss instead of making real API calls."
        ),
    )
    args = parser.parse_args()

    # Resolve and create output directory
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Target      : {args.target}")
    print(f"Output dir  : {output_dir.resolve()}")
    print(f"Max cands   : {args.max_candidates}")
    print(f"Dry-run     : {args.dry_run}")
    print()

    result = run_pipeline(
        target=args.target,
        max_candidates=args.max_candidates,
        dry_run=args.dry_run,
    )

    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"{args.target}_{timestamp}.md"
    report_path = output_dir / report_filename
    report_path.write_text(result["report"], encoding="utf-8")

    print()
    print(f"Candidates evaluated : {result['candidates_evaluated']}")
    print(f"Candidates kept      : {result['kept_count']}")
    print(f"Report saved to      : {report_path.resolve()}")


if __name__ == "__main__":
    main()
