"""Provider failures that must not be mistaken for valid empty model output."""


class ModelResponseError(RuntimeError):
    def __init__(self, reason: str, *, cost: float = 0.0):
        super().__init__(f"Model response was not usable: {reason}")
        self.reason = reason
        self.cost = cost
