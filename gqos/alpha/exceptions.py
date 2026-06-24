class FeatureDependencyCycleError(Exception):
    def __init__(self, message: str):
        super().__init__(f"Feature Dependency Cycle Detected: {message}")

class MissingFeatureDependencyError(Exception):
    def __init__(self, feature_id: str, missing_id: str):
        super().__init__(f"Feature '{feature_id}' is missing dependency '{missing_id}'")
