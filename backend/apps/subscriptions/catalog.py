from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDef:
    code: str
    name: str
    is_limit: bool = False
    description: str = ""


FEATURES: tuple[FeatureDef, ...] = (
    FeatureDef("branches", "Branches", is_limit=True, description="Maximum number of branches."),
    FeatureDef("members", "Members", is_limit=True, description="Maximum active members."),
    FeatureDef("custom_roles", "Custom roles"),
    FeatureDef("custom_branding", "Custom branding"),
    FeatureDef("audit_log", "Audit log"),
    FeatureDef("products", "Products and catalog"),
    FeatureDef("recipes", "Recipes and costing"),
    FeatureDef("pos", "Point of sale"),
    FeatureDef("inventory", "Inventory"),
    FeatureDef("purchasing", "Purchasing"),
    FeatureDef("production", "Production"),
    FeatureDef("expenses", "Expenses and approvals"),
    FeatureDef("finance_reports", "Financial reports"),
)

ALL_MODULES = {
    "products",
    "recipes",
    "pos",
    "inventory",
    "purchasing",
    "production",
    "expenses",
    "finance_reports",
}

# Defaults created by ``bootstrap_platform`` when a plan does not exist yet; editable afterwards.
DEFAULT_PLANS: dict[str, dict] = {
    "starter": {
        "name": "Starter",
        "trial_days": 14,
        "entitlements": {
            "branches": 1,
            "members": 5,
            "custom_branding": True,
            "audit_log": True,
            "products": True,
            "pos": True,
            "inventory": True,
            "expenses": True,
        },
    },
    "growth": {
        "name": "Growth",
        "trial_days": 14,
        "entitlements": {
            "branches": 5,
            "members": 30,
            "custom_roles": True,
            "custom_branding": True,
            "audit_log": True,
            **{module: True for module in ALL_MODULES},
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "trial_days": 0,
        "entitlements": {
            "branches": None,
            "members": None,
            "custom_roles": True,
            "custom_branding": True,
            "audit_log": True,
            **{module: True for module in ALL_MODULES},
        },
    },
}
