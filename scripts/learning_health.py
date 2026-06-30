import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gqos.ops.learning_health import build_learning_health


def main() -> int:
    ok, report = build_learning_health()
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
