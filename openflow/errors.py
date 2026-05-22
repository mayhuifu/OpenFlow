"""OpenFlow exception hierarchy."""


class OpenFlowError(Exception):
    """Base class for all OpenFlow exceptions."""


class InstrumentConnectError(OpenFlowError):
    """Raised by an instrument fixture when the VISA session cannot be opened."""

    def __init__(self, resource: str, cause: str) -> None:
        super().__init__(f"Failed to connect to instrument at {resource!r}: {cause}")
        self.resource = resource
        self.cause = cause


class MigrationError(OpenFlowError):
    """Raised by the migration CLI when an input file cannot be transformed."""
