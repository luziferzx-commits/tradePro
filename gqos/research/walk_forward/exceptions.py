class DataLeakageError(Exception):
    def __init__(self, message: str):
        super().__init__(f"Data Leakage Detected: {message}")
