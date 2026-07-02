"""Supervisor: keep the GQOS live engine running (auto-relaunch on exit/crash).

Run this INSTEAD of launching run_gqos_live directly:

    python -m scripts.run_supervisor

It relaunches the engine whenever it exits. A crash-loop guard backs off (and
eventually stops) if the engine keeps dying immediately, so a broken build
doesn't spin forever.
"""
import os
import sys
import time
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - SUPERVISOR - %(message)s")
logger = logging.getLogger("Supervisor")

_ENGINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_gqos_live.py")
CHILD_CMD = [sys.executable, _ENGINE]
# A run shorter than this counts as an early crash.
MIN_HEALTHY_RUNTIME_SEC = 60
# Stop after this many consecutive early crashes.
MAX_CONSECUTIVE_CRASHES = 5
BACKOFF_BASE_SEC = 5


def run(cmd=CHILD_CMD, run_child=None):
    """run_child(cmd) -> (exit_code, runtime_sec); injectable for tests."""
    if run_child is None:
        def run_child(c):
            start = time.time()
            proc = subprocess.Popen(c)
            proc.wait()
            return proc.returncode, time.time() - start

    consecutive_crashes = 0
    while True:
        logger.info("Launching engine: %s", " ".join(cmd))
        code, runtime = run_child(cmd)

        if runtime >= MIN_HEALTHY_RUNTIME_SEC:
            consecutive_crashes = 0
            logger.warning("Engine exited (code=%s) after %.0fs — relaunching.", code, runtime)
        else:
            consecutive_crashes += 1
            logger.error(
                "Engine crashed early (code=%s, %.0fs) — crash %d/%d.",
                code, runtime, consecutive_crashes, MAX_CONSECUTIVE_CRASHES,
            )
            if consecutive_crashes >= MAX_CONSECUTIVE_CRASHES:
                logger.critical("Too many consecutive early crashes — supervisor stopping. Fix the engine and restart.")
                return 1

        backoff = BACKOFF_BASE_SEC * max(1, consecutive_crashes)
        logger.info("Restarting in %ds...", backoff)
        time.sleep(backoff)


if __name__ == "__main__":
    try:
        sys.exit(run())
    except KeyboardInterrupt:
        logger.info("Supervisor stopped by user.")
