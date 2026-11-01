"""Exceptions the bot treats as recoverable at handler boundaries.

py-tgcalls errors share no base class, so they are collected from its exceptions module.
"""

from __future__ import annotations

from pytgcalls import exceptions as tgcalls_exceptions
from telethon.errors import RPCError
from yt_dlp.utils import YoutubeDLError

RECOVERABLE_ERRORS: tuple[type[Exception], ...] = (
    RPCError,
    YoutubeDLError,
    OSError,
    RuntimeError,
    ValueError,
    *(
        cls
        for cls in vars(tgcalls_exceptions).values()
        if isinstance(cls, type)
        and issubclass(cls, Exception)
        and cls.__module__ == tgcalls_exceptions.__name__
    ),
)
