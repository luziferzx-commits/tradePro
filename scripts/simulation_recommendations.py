import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gqos.learning.simulation_analyzer import build_simulation_recommendations


def main() -> int:
    payload = build_simulation_recommendations()
    print(f"Virtual rows: {payload['virtual_rows']}")
    print(f"Missed rows: {payload['missed_rows']}")
    print(f"Recommendations: {len(payload['recommendations'])}")
    for key, rec in list(payload["recommendations"].items())[:20]:
        print(
            f"{key}: {rec['action']} samples={rec['samples']} "
            f"WR={rec['win_rate']:.1%} AvgR={rec['avg_r']:+.2f} "
            f"PFadj={rec['pf_threshold_adjust']:+.3f} ExpAdj={rec['expectancy_threshold_adjust']:+.3f}"
        )
    context = payload.get("context_recommendations", {})
    print(f"Context recommendations: {len(context)}")
    for key, rec in list(context.items())[:20]:
        print(
            f"{key}: {rec['action']} samples={rec['samples']} "
            f"WR={rec['win_rate']:.1%} AvgR={rec['avg_r']:+.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
