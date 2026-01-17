import logging

from .client import Client
from .exceptions import LazyestsError
from .logger import setup_logging
from .response import Response

__version__ = "1.0.0"

# Add NullHandler to prevent logging warnings if no handler is configured by the user.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["Client", "Response", "LazyestsError", "setup_logging"]
