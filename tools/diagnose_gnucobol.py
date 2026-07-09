"""Diagnostic utility for GnuCOBOL subprocess startup."""

from __future__ import annotations

import os
import subprocess

from opencobol2.toolchains import gnucobol


def main() -> int:
    """Run real probes and expose subprocess startup failures."""
    environment = dict(os.environ)

    print("OpenCobol2 GnuCOBOL Probe Diagnostic")
    print("=" * 70)

    for candidate in gnucobol._iter_candidates(
        explicit_path=None,
        environment=environment,
    ):
        if not candidate.path.is_file():
            continue

        print()
        print(f"Compiler: {candidate.path}")
        print(f"Source:   {candidate.source}")

        probe_environment = gnucobol._build_candidate_environment(
            candidate.path,
            environment,
        )

        for argument in ("--version", "--info"):
            print()
            print(f"Running {argument}")

            try:
                completed_process = subprocess.run(
                    [
                        str(candidate.path),
                        argument,
                    ],
                    env=probe_environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    timeout=10,
                    check=False,
                )
            except Exception as error:
                print(f"FAILED: {type(error).__name__}")
                print(f"MESSAGE: {error}")
                continue

            print(f"RETURN CODE: {completed_process.returncode}")
            print("OUTPUT:")
            print(completed_process.stdout)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())