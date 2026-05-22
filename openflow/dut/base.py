"""DUT base class — port of UMT_DUTs.UMT_DUT minus OpenTAP scaffolding.

V1a ships this base only; concrete DUTs (e.g. DUT_U300) land in V1b once
DUT_FT2232H and DUT_U300 are ported from the existing UMT_DUTs package.

The `__getattr__` fallback lets the migrated TX EVM test *collect* even
though it calls methods like `set_rfTxPower` that the real DUT will implement
in V1b — collection succeeds because the attribute lookup returns a callable;
actually calling that callable raises a clear NotImplementedError.
"""
from __future__ import annotations

import logging
from typing import Any


class Dut:
    """Base for all DUT subclasses. Mirrors UMT_DUTs.UMT_DUT — minus OpenTAP."""

    def __init__(self) -> None:
        self.log = logging.getLogger(__name__)
        self.emulation = False
        self.name = type(self).__name__

    def open(self) -> None:
        """Called when a test plan starts. Base no-op; subclasses override."""
        self.log.info("%s.open() — base no-op", self.name)

    def close(self) -> None:
        """Called when a test plan ends. Base no-op; subclasses override."""
        self.log.info("%s.close() — base no-op", self.name)

    def get_id(self) -> str:
        """Return the DUT's ID. Base returns a placeholder; subclasses override."""
        self.log.warning("Dut.get_id() not implemented by subclass; returning placeholder")
        return "No_ID"

    def __getattr__(self, name: str) -> Any:
        # Only reached when normal attribute lookup fails. This lets the migrated
        # TX EVM test collect — it references methods like set_rfTxPower that
        # are defined by the V1b concrete DUT (DUT_U300) but not yet here.
        def _unimplemented(*args: object, **kwargs: object) -> None:
            raise NotImplementedError(
                f"Dut.{name}() — V1a base class. "
                f"Concrete DUT (e.g. DUT_U300) lands in V1b.")
        return _unimplemented
