"""
botlite.handlers
~~~~~~~~~~~~~~~~
Import this module to register all Telethon event handlers.
"""

# Side-effect imports — decorators register handlers on the client
from botlite.handlers import commands, url

__all__ = ["commands", "url"]
