"""
Módulo de Estandarización de Zona Horaria para SAGES.
Zona horaria oficial de la República Bolivariana de Venezuela: America/Caracas (UTC-4).
"""
from datetime import datetime, timezone, timedelta, date, time
from typing import Optional, Tuple, Union

try:
    from zoneinfo import ZoneInfo
    try:
        CARACAS_TZ = ZoneInfo("America/Caracas")
    except Exception:
        CARACAS_TZ = timezone(timedelta(hours=-4), name="America/Caracas")
except ImportError:
    CARACAS_TZ = timezone(timedelta(hours=-4), name="America/Caracas")


def get_caracas_now() -> datetime:
    """Retorna la fecha y hora actual en la zona horaria oficial de Venezuela (UTC-4)."""
    return datetime.now(CARACAS_TZ)


def get_caracas_today() -> date:
    """
    Retorna la fecha calendario actual (date) en Venezuela (America/Caracas).
    Garantiza que la transición de día ocurra estrictamente a las 12:00 AM (medianoche)
    hora de Venezuela, y no con desfase de UTC (8:00 PM del día previo).
    """
    return get_caracas_now().date()


def to_caracas_time(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convierte un objeto datetime (asumiendo UTC si es naive) a la zona horaria de Venezuela.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CARACAS_TZ)


def caracas_date_range_to_utc(
    date_from_val: Optional[Union[str, date]], 
    date_to_val: Optional[Union[str, date]]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Convierte límites de fechas locales de Venezuela ('YYYY-MM-DD' o date) a sus
    equivalentes exactos en UTC para consultas de base de datos en campos DateTime(timezone=True).
    
    Ejemplo:
        date_from = '2026-11-08' -> 2026-11-08 00:00:00-04:00 -> 2026-11-08 04:00:00 UTC
        date_to   = '2026-11-08' -> 2026-11-08 23:59:59.999999-04:00 -> 2026-11-09 03:59:59.999999 UTC
    """
    start_utc = None
    end_utc = None

    if date_from_val:
        try:
            if isinstance(date_from_val, str):
                d_from = datetime.strptime(date_from_val.strip(), "%Y-%m-%d").date()
            else:
                d_from = date_from_val
            start_local = datetime.combine(d_from, time.min).replace(tzinfo=CARACAS_TZ)
            start_utc = start_local.astimezone(timezone.utc)
        except (ValueError, TypeError):
            start_utc = None

    if date_to_val:
        try:
            if isinstance(date_to_val, str):
                d_to = datetime.strptime(date_to_val.strip(), "%Y-%m-%d").date()
            else:
                d_to = date_to_val
            end_local = datetime.combine(d_to, time.max).replace(tzinfo=CARACAS_TZ)
            end_utc = end_local.astimezone(timezone.utc)
        except (ValueError, TypeError):
            end_utc = None

    return start_utc, end_utc

