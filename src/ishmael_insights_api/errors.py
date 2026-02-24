from __future__ import annotations


class IshmaelInsightsAPIError(Exception):
    """Raised when the Ishmael Insights API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str, payload: object | None = None):
        super().__init__(f"{status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.payload = payload
