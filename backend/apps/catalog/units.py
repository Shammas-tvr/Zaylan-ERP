"""Convert recipe quantities into an item's base unit (grams, millilitres, or each)."""

from decimal import Decimal, ROUND_HALF_UP

from rest_framework.exceptions import ValidationError

MASS = frozenset({"G", "KG"})
VOLUME = frozenset({"ML", "L"})
COUNT = frozenset({"EACH", "PACKET", "BOTTLE", "TRAY"})
FACTORS = {
    "G": Decimal("1"),
    "KG": Decimal("1000"),
    "ML": Decimal("1"),
    "L": Decimal("1000"),
    "EACH": Decimal("1"),
    "PACKET": Decimal("1"),
    "BOTTLE": Decimal("1"),
    "TRAY": Decimal("1"),
}
QUANTUM = Decimal("0.001")


def from_base(quantity, item) -> Decimal:
    """Convert a ledger quantity into the item's stock unit."""
    factor = stock_factor(item.stock_unit or item.base_unit)
    return (Decimal(quantity) / factor).quantize(QUANTUM, rounding=ROUND_HALF_UP)


def stock_factor(stock_unit: str) -> Decimal:
    """How many ledger base units are in one of the item's stock units."""
    unit = (stock_unit or "").upper()
    if unit == "BOX":
        return Decimal("1")
    if unit not in FACTORS:
        raise ValidationError({"unit": ["Unknown unit."]})
    return FACTORS[unit]


def quantity_in_base(quantity, unit: str, item) -> Decimal:
    """Convert a counted quantity into the item's ledger unit (G, ML, or EACH)."""
    unit = (unit or "").upper()
    if unit == "BOX":
        per_stock = Decimal(item.purchase_factor or 1)
        if (item.purchase_unit or "").upper() != "BOX":
            per_stock = Decimal("1")
        value = (Decimal(quantity) * per_stock * stock_factor(item.stock_unit or item.base_unit)).quantize(
            QUANTUM, rounding=ROUND_HALF_UP
        )
        if value <= 0:
            raise ValidationError({"quantity": ["Quantity must be greater than zero."]})
        return value
    return to_base(quantity, unit, item.base_unit)


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
