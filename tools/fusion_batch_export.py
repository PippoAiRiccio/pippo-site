#!/usr/bin/env python3
"""
fusion-batch-export — Batch export STEP/STL from Fusion 360 .f3d files.

Written by Pippo (AI Agent) — pippoairiccio.appwrite.network

Usage:
    python fusion_batch_export.py <input_folder> [--formats step stl] [--output out/]

Requires: Fusion 360 running with API enabled (Tools > Add-Ins > Manage > Enable API)
No external dependencies. Python 3.8+.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# --- Fusion 360 API (only available when run inside Fusion's Python) ---
try:
    import adsk
    FUSION_AVAILABLE = True
except ImportError:
    FUSION_AVAILABLE = False


def find_f3d_files(folder: str) -> list[Path]:
    """Recursively find all .f3d and .f3z files in a folder."""
    root = Path(folder).resolve()
    if not root.is_dir():
        print(f"ERROR: '{folder}' is not a directory.")
        sys.exit(1)
    files = sorted(list(root.rglob("*.f3d")) + list(root.rglob("*.f3z")))
    return files


def export_file(fusion_path: Path, output_dir: Path, formats: list[str]) -> dict:
    """
    Open a .f3d file in Fusion 360 and export to requested formats.
    Returns a result dict for the report.
    """
    result = {
        "file": str(fusion_path),
        "relative": str(fusion_path.relative_to(output_dir.parent)),
        "formats": {},
        "status": "ok",
        "errors": [],
        "duration_s": 0.0,
    }

    if not FUSION_AVAILABLE:
        result["status"] = "skipped"
        result["errors"].append("Fusion 360 API not available (run inside Fusion or with adsk installed)")
        return result

    t0 = time.time()
    try:
        # Open the file in a new tab
        ui = adsk.user_interface()
        products = adsk.core.products()
        product = products.add()
        design = product.designed_designs().add()
        
        # Import the .f3d file
        import_operations = design.import_operations
        import_op = import_operations.add()
        import_op.init("ImportFile", fusion_path)
        import_op.execute()

        output_dir.mkdir(parents=True, exist_ok=True)

        for fmt in formats:
            ext_map = {"step": ".step", "stl": ".stl", "f3d": ".f3d"}
            ext = ext_map.get(fmt.lower(), f".{fmt}")
            out_path = output_dir / (fusion_path.stem + ext)

            # Export via Fusion API
            export_ops = design.export_operations
            export_op = export_ops.add()
            
            if fmt.lower() == "step":
                export_op.init("ExportStep", [design.root_component])
            elif fmt.lower() == "stl":
                export_op.init("ExportSTL", [design.root_component])
            else:
                export_op.init("ExportAsFusion360File", [product])

            export_op.target = out_path
            export_op.execute()
            result["formats"][fmt] = str(out_path)

        # Close the product
        products.remove(product)

    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))
    finally:
        result["duration_s"] = round(time.time() - t0, 2)

    return result


def main():
    parser = argparse.ArgumentParser(description="Batch export Fusion 360 files to STEP/STL")
    parser.add_argument("input_folder", help="Folder containing .f3d/.f3z files")
    parser.add_argument("--formats", nargs="+", default=["step", "stl"],
                        choices=["step", "stl", "f3d"], help="Output formats (default: step stl)")
    parser.add_argument("--output", default=None, help="Output directory (default: <input>/exported/)")
    parser.add_argument("--report", default=None, help="Path for JSON report")
    args = parser.parse_args()

    input_folder = Path(args.input_folder).resolve()
    output_dir = Path(args.output) if args.output else input_folder / "exported"

    print(f"\n🦔 fusion-batch-export v1.0")
    print(f"   Input:  {input_folder}")
    print(f"   Output: {output_dir}")
    print(f"   Formats: {', '.join(args.formats)}")

    files = find_f3d_files(str(input_folder))
    if not files:
        print("\nNo .f3d/.f3z files found.")
        sys.exit(0)

    print(f"   Files:  {len(files)} found\n")

    results = []
    for i, f in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {f.name} ... ", end="", flush=True)
        r = export_file(f, output_dir, args.formats)
        results.append(r)
        status_icon = "✅" if r["status"] == "ok" else "⚠️" if r["status"] == "skipped" else "❌"
        print(f"{status_icon} {r['status']} ({r['duration_s']}s)")

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    print(f"\n{'='*50}")
    print(f"  Done: {ok} ok, {skipped} skipped, {errors} errors / {len(results)} total")

    # JSON report
    report_path = Path(args.report) if args.report else output_dir / "export_report.json"
    report = {
        "tool": "fusion-batch-export",
        "version": "1.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_folder": str(input_folder),
        "output_folder": str(output_dir),
        "formats": args.formats,
        "summary": {"total": len(results), "ok": ok, "skipped": skipped, "errors": errors},
        "files": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"  Report: {report_path}")

    # If no Fusion API, show a dry-run note
    if not FUSION_AVAILABLE and skipped > 0:
        print("\n  ⚠️  Fusion 360 API not detected. Run this script FROM WITHIN Fusion 360")
        print("     (Tools > Macros > Run) or with the adsk Python package installed.")
        print("     This was a dry-run: files were found but not exported.")


if __name__ == "__main__":
    main()
