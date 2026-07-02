"""Request a supervised engine restart by dropping the restart flag.

The running engine polls for this file and exits gracefully when it appears;
the supervisor then relaunches it with the new config. Use after a structural
config change (symbol enable/disable, EOD hour, etc.) that hot-reload can't
apply live.

    python -m scripts.request_restart
"""
import os

FLAG = os.getenv("GQOS_RESTART_FLAG", os.path.join("data", "execution", "restart.flag"))


def request_restart(flag_path: str = FLAG) -> str:
    directory = os.path.dirname(flag_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write("restart requested")
    return flag_path


if __name__ == "__main__":
    path = request_restart()
    print(f"Restart requested (flag written: {path}). The supervisor will relaunch the engine shortly.")
