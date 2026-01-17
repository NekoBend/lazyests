"""Custom exceptions for lazyests module."""


class LazyestsError(Exception):
    """Base exception class for all lazyests exceptions.

    All custom exceptions in this library should inherit from this class.
    This allows users to catch all library-specific errors with a single except block.
    """


class BrowserInitError(LazyestsError):
    """Raised when the browser initialization fails.

    This error indicates that the underlying browser process (Chromium)
    could not be started or connected to.

    Common causes include:
    - Missing browser executable
    - Port conflicts
    - Invalid profile directory permissions
    - Incompatible Chromium version
    """


class AuthError(LazyestsError):
    """Raised when authentication fails or session expires.

    This exception is raised when the client detects that the current session
    is no longer valid (e.g., 401/403 responses or redirection to a login page).

    It typically serves as a signal that manual intervention (handoff)
    might be required to restore the session.
    """
