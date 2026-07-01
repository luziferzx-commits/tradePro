import MetaTrader5 as mt5

from config.settings import settings


def ensure_mt5_initialized() -> bool:
    if mt5.account_info() is not None:
        return True
    kwargs = {
        "login": settings.MT5_LOGIN,
        "password": settings.MT5_PASSWORD,
        "server": settings.MT5_SERVER,
    }
    if getattr(settings, "MT5_PATH", ""):
        kwargs["path"] = settings.MT5_PATH
    try:
        return bool(mt5.initialize(**kwargs))
    except Exception:
        return False
