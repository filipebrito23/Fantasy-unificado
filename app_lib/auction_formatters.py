from __future__ import annotations

from datetime import datetime, timezone


def valor_por_extenso(value):
    try:
        value = float(value or 0)
    except Exception:
        value = 0.0
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_brl(value):
    return valor_por_extenso(value)


def format_remaining(expires_at):
    if expires_at is None or expires_at == "" or (isinstance(expires_at, float) and expires_at != expires_at):
        return "-"
    if isinstance(expires_at, (int, float)):
        return "-"
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except Exception:
            return "-"
    if not hasattr(expires_at, "tzinfo"):
        return "-"
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = expires_at - now
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "Encerrado"
    hours, rem = divmod(total_seconds, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{hours}h {minutes:02d}m"