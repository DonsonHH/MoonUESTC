class ToolError(Exception):
    """Only stable, non-sensitive reason/stage values cross the CLI boundary."""
    def __init__(self, reason, stage="local", api_code=None):
        super().__init__(reason)
        self.reason, self.stage, self.api_code = reason, stage, api_code


class AuthRequired(ToolError):
    pass
