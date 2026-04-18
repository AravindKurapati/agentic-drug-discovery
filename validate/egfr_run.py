import subprocess
import sys
from pathlib import Path


def test_dry_run_smoke(tmp_path):
    project_root = Path(__file__).resolve().parent.parent

    # Seed a dummy cache entry so dry-run doesn't raise a cache-miss error
    cache_dir = tmp_path / ".nim_cache"
    cache_dir.mkdir()
    (cache_dir / "dummy.json").write_text("{}")

    output_dir = tmp_path / "reports"
    output_dir.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "app.py"),
            "--dry-run",
            "--target", "P00533",
            "--output-dir", str(output_dir),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"app.py exited with code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    md_files = list(output_dir.glob("*.md"))
    assert len(md_files) == 1, f"Expected 1 .md file, found {len(md_files)}: {md_files}"

    report_text = md_files[0].read_text(encoding="utf-8")
    assert "# Drug Discovery Report \u2014 P00533" in report_text, (
        f"Report header not found in:\n{report_text}"
    )
    assert "Dry-run mode" in report_text, (
        f"'Dry-run mode' not found in:\n{report_text}"
    )
