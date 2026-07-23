"""Render `pyrefly coverage report`'s JSON as a human-readable table.

Reads the JSON report from stdin (i.e. run as
``pyrefly coverage report src | python scripts/pyrefly_coverage_summary.py``) and
prints one row per module -- typable symbol count, how many are untyped, and the
resulting coverage percentage -- followed by the same metrics summed across the
whole project.
"""

import json
import sys


def _coverage(n_typable: int, n_untyped: int) -> float:
    if n_typable == 0:
        return 100.0
    return 100.0 * (n_typable - n_untyped) / n_typable


def main() -> None:
    """Read a pyrefly coverage JSON report from stdin and print a summary table."""
    report = json.load(sys.stdin)

    rows = sorted(
        (
            module["name"],
            module["n_typable"],
            module["n_untyped"],
            _coverage(module["n_typable"], module["n_untyped"]),
        )
        for module in report["module_reports"]
    )

    name_width = max((len(name) for name, *_ in rows), default=len("Module"))
    header = (
        f"{'Module':<{name_width}}  {'Typable':>7}  {'Untyped':>7}  {'Coverage':>8}"
    )
    print(header)
    print("-" * len(header))
    for name, n_typable, n_untyped, coverage in rows:
        print(
            f"{name:<{name_width}}  {n_typable:>7}  {n_untyped:>7}  {coverage:>7.1f}%"
        )

    summary = report["summary"]
    print("-" * len(header))
    print(
        f"{'TOTAL':<{name_width}}  {summary['n_typable']:>7}  "
        f"{summary['n_untyped']:>7}  {summary['coverage']:>7.1f}%"
    )


if __name__ == "__main__":
    main()
