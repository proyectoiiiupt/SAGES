"""
=============================================================================
SAGES - Módulo Oficial de Días Feriados Nacionales de Venezuela
=============================================================================
Define los días feriados de conformidad con:
- Ley Orgánica del Trabajo, los Trabajadores y las Trabajadoras (LOTTT), Art. 184.
- Ley de Fiestas Nacionales.

Incluye feriados nacionales fijos y feriados móviles eclesiásticos
(Carnaval, Jueves Santo y Viernes Santo) calculados automáticamente
mediante el algoritmo de Butcher / Meeus para la Pascua Gregoriana.
=============================================================================
"""

from datetime import date, timedelta
from typing import Dict, Optional


def get_easter_date(year: int) -> date:
    """
    Calcula la fecha del Domingo de Resurrección (Pascua) para un año dado
    usando el algoritmo de Butcher para el calendario gregoriano.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_venezuela_holidays(year: int) -> Dict[date, str]:
    """
    Retorna un diccionario mapeando cada fecha (objeto date) con el nombre
    del feriado nacional venezolano correspondiente.
    """
    holidays: Dict[date, str] = {}

    # 1. Feriados Fijos Oficiales (LOTTT Art. 184 y Ley de Fiestas Nacionales)
    fixed_holidays = [
        (1, 1, "Año Nuevo"),
        (4, 19, "Declaración de la Independencia (19 de Abril)"),
        (5, 1, "Día Internacional del Trabajador"),
        (6, 24, "Batalla de Carabobo"),
        (7, 5, "Día de la Independencia (5 de Julio)"),
        (7, 24, "Natalicio del Libertador Simón Bolívar"),
        (10, 12, "Día de la Resistencia Indígena"),
        (12, 24, "Víspera de Navidad"),
        (12, 25, "Navidad"),
        (12, 31, "Fin de Año"),
    ]

    for m, d, name in fixed_holidays:
        try:
            holidays[date(year, m, d)] = name
        except ValueError:
            pass

    # 2. Feriados Móviles (Carnavales y Semana Santa)
    easter = get_easter_date(year)
    
    # Lunes y Martes de Carnaval (48 y 47 días antes de Pascua)
    carnaval_lunes = easter - timedelta(days=48)
    carnaval_martes = easter - timedelta(days=47)
    holidays[carnaval_lunes] = "Lunes de Carnaval"
    holidays[carnaval_martes] = "Martes de Carnaval"

    # Jueves y Viernes Santo (3 y 2 días antes de Pascua)
    jueves_santo = easter - timedelta(days=3)
    viernes_santo = easter - timedelta(days=2)
    holidays[jueves_santo] = "Jueves Santo"
    holidays[viernes_santo] = "Viernes Santo"

    return holidays


def get_venezuela_holidays_for_month(year: int, month: int) -> Dict[str, str]:
    """
    Retorna los feriados de un año y mes específicos en formato string:
    {"YYYY-MM-DD": "Nombre del Feriado"}.
    Ideal para ser serializado como JSON en endpoints API.
    """
    year_holidays = get_venezuela_holidays(year)
    result: Dict[str, str] = {}

    for d, name in year_holidays.items():
        if d.month == month:
            result[d.strftime("%Y-%m-%d")] = name

    return result


def is_venezuela_holiday(d: date) -> bool:
    """
    Determina si una fecha dada corresponde a un día feriado nacional en Venezuela.
    """
    if not isinstance(d, date):
        return False
    year_holidays = get_venezuela_holidays(d.year)
    return d in year_holidays


def get_holiday_name(d: date) -> Optional[str]:
    """
    Retorna el nombre del feriado si la fecha es un día feriado nacional, o None si es hábil.
    """
    if not isinstance(d, date):
        return None
    year_holidays = get_venezuela_holidays(d.year)
    return year_holidays.get(d)


def is_business_day(d: date) -> bool:
    """
    Retorna True si la fecha es un día hábil laboral (lunes a viernes y no feriado nacional).
    """
    if not isinstance(d, date):
        return False
    if d.weekday() >= 5:  # Sábado (5) o Domingo (6)
        return False
    return not is_venezuela_holiday(d)
