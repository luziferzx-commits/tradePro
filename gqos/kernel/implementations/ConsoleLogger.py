import logging
from gqos.kernel.interfaces import ILogger

class ConsoleLogger(ILogger):
    """
    Basic Console Logger implementation.
    """
    def __init__(self, name: str = "GQOS"):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

    def log(self, level: str, message: str) -> None:
        if level == "INFO":
            self.logger.info(message)
        elif level == "DEBUG":
            self.logger.debug(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "CRITICAL":
            self.logger.critical(message)
        else:
            self.logger.info(f"[{level}] {message}")
