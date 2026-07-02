import logging
import socket

logger = logging.getLogger(__name__)


class SingleInstanceLock:
    """Process lifetime lock backed by a localhost TCP port."""

    def __init__(self, name: str, port: int, host: str = "127.0.0.1"):
        self.name = name
        self.host = host
        self.port = int(port)
        self._socket = None

    def acquire(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind((self.host, self.port))
            sock.listen(1)
        except OSError as exc:
            sock.close()
            logger.error(
                "%s is already running or lock port is unavailable (%s:%s): %s",
                self.name,
                self.host,
                self.port,
                exc,
            )
            return False

        self._socket = sock
        logger.info("%s single-instance lock acquired on %s:%s", self.name, self.host, self.port)
        return True

    def release(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None
                logger.info("%s single-instance lock released", self.name)
