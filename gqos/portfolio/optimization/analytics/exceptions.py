class RegressionDriftDetectedError(Exception):
    def __init__(self, expected_hash: str, actual_hash: str):
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(f"Optimizer Regression Drift Detected! Expected Hash: {expected_hash}, Actual Hash: {actual_hash}")
