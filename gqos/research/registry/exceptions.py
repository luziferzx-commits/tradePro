class ExperimentAlreadyExistsError(Exception):
    def __init__(self, experiment_id: str):
        super().__init__(f"Experiment {experiment_id} already exists. Overwrite not allowed.")

class ArtifactTamperedError(Exception):
    def __init__(self, message: str):
        super().__init__(f"Artifact Tampered: {message}")
