"""Application-wide exception hierarchy."""


class OmraError(Exception):
    """Base class for errors that callers may handle at an OMRA boundary."""
