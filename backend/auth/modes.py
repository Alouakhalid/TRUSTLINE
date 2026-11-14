"""Request mode dependency: operational vs demo, resolved from a signed header."""
from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException


def demo_mode(x_trustline_mode: str | None = Header(default=None)) -> bool:
    """True when the caller is operating in the isolated demo environment."""
    value = (x_trustline_mode or "operational").lower()
    if value not in {"operational", "demo"}:
        raise HTTPException(status_code=400, detail="X-Trustline-Mode must be operational or demo")
    return value == "demo"
