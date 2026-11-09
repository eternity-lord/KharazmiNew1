"""Deterministic route-audit clock for server modules that call wall-clock APIs."""
from __future__ import annotations

import datetime as _datetime
import sys
import time as _time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Kharazmi_Server"
FIXED_NOW = _datetime.datetime(2026, 9, 28, 9, 0, 0)
_REAL_DATETIME = _datetime.datetime
_REAL_DATE = _datetime.date
_REAL_TIME = _datetime.time
_REAL_TIMEDELTA = _datetime.timedelta
_REAL_TIMEZONE = _datetime.timezone


class FrozenDateTime(_REAL_DATETIME):
    @classmethod
    def now(cls, tz=None):
        value = cls(FIXED_NOW.year, FIXED_NOW.month, FIXED_NOW.day,
                    FIXED_NOW.hour, FIXED_NOW.minute, FIXED_NOW.second,
                    FIXED_NOW.microsecond)
        return value.replace(tzinfo=tz) if tz is not None else value

    @classmethod
    def utcnow(cls):
        return cls(FIXED_NOW.year, FIXED_NOW.month, FIXED_NOW.day,
                   FIXED_NOW.hour, FIXED_NOW.minute, FIXED_NOW.second,
                   FIXED_NOW.microsecond)

    @classmethod
    def today(cls):
        return cls.now()


class FrozenDate(_REAL_DATE):
    @classmethod
    def today(cls):
        return cls(FIXED_NOW.year, FIXED_NOW.month, FIXED_NOW.day)


_FROZEN_DATETIME_MODULE = SimpleNamespace(
    datetime=FrozenDateTime,
    date=FrozenDate,
    time=_REAL_TIME,
    timedelta=_REAL_TIMEDELTA,
    timezone=_REAL_TIMEZONE,
)
_FIXED_EPOCH = FIXED_NOW.replace(tzinfo=_REAL_TIMEZONE.utc).timestamp()
_FROZEN_TIME_MODULE = SimpleNamespace(
    time=lambda: _FIXED_EPOCH,
    monotonic=_time.monotonic,
    perf_counter=_time.perf_counter,
    sleep=_time.sleep,
    strftime=_time.strftime,
    localtime=_time.localtime,
    gmtime=_time.gmtime,
    mktime=_time.mktime,
)


def freeze_loaded_server_modules():
    """Patch wall-clock names in already-imported server modules; return undo."""
    # The summary helpers are imported lazily by several endpoints, so load them
    # before scanning the package modules. Their imported functions then share the
    # same module-global clock proxy as the route handlers.
    if str(SERVER) not in sys.path:
        sys.path.insert(0, str(SERVER))
    import today_summary  # type: ignore  # noqa: F401

    changes: list[tuple[object, str, object]] = []
    server_root = str(SERVER.resolve())
    for module in list(sys.modules.values()):
        if module is None:
            continue
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        try:
            if not Path(module_file).resolve().is_relative_to(server_root):
                continue
        except (OSError, ValueError):
            continue
        for attr in ("datetime", "date", "time", "time_module"):
            value = getattr(module, attr, None)
            replacement = None
            if attr == "datetime" and value is _datetime:
                replacement = _FROZEN_DATETIME_MODULE
            elif attr == "datetime" and value is _REAL_DATETIME:
                replacement = FrozenDateTime
            elif attr == "date" and value is _REAL_DATE:
                replacement = FrozenDate
            elif attr in ("time", "time_module") and value is _time:
                replacement = _FROZEN_TIME_MODULE
            if replacement is not None:
                changes.append((module, attr, value))
                setattr(module, attr, replacement)

    def restore() -> None:
        for module, attr, value in reversed(changes):
            setattr(module, attr, value)

    return restore
