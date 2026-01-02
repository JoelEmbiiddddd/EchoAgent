class ArtifactError(Exception):
    pass


class ArtifactConfigError(ArtifactError):
    pass


class ArtifactWriteError(ArtifactError):
    pass
