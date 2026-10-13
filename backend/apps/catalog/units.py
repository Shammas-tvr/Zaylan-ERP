"""Convert recipe quantities into an item's base unit (grams, millilitres, or each)."""

from decimal import Decimal, ROUND_HALF_UP

from rest_framework.exceptions import ValidationError

MASS = frozenset({"G", "KG"})
VOLUME = frozenset({"ML", "L"})
COUNT = frozenset({"EACH"})
FACTORS = {
    "G": Decimal("1"),
    "KG": Decimal("1000"),
    "ML": Decimal("1"),
    "L": Decimal("1000"),
    "EACH": Decimal("1"),
}
QUANTUM = Decimal("0.001")


def to_base(quantity, unit: str, base_unit: str) -> Decimal:
    unit = (unit or "").upper()
    base_unit = (base_unit or "").upper()
    if unit not in FACTORS or base_unit not in FACTORS:
        raise ValidationError({"unit": ["Unknown unit."]})
    same_family = (
        (unit in MASS and base_unit in MASS)
        or (unit in VOLUME and base_unit in VOLUME)
        or (unit in COUNT and base_unit in COUNT)
    )
    if not same_family:
        raise ValidationError({"unit": [f"{unit} cannot be converted to {base_unit}."]})
    value = (Decimal(quantity) * FACTORS[unit] / FACTORS[base_unit]).quantize(
        QUANTUM, rounding=ROUND_HALF_UP
    )
    if value <= 0:
        raise ValidationError({"quantity": ["Quantity must be greater than zero."]})
    return value
