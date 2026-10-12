from rest_framework import serializers

from apps.expenses.models import (
    Expense,
    ExpenseCategory,
    ExpenseStatus,
    PaymentMethod,
    RecurringExpense,
    RecurringFrequency,
)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ("id", "code", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ExpenseCategoryWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=150)
    is_active = serializers.BooleanField(required=False, default=True)


class RecurringExpenseSerializer(serializers.ModelSerializer):
    branch_id = serializers.UUIDField(source="branch.id", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    category_id = serializers.UUIDField(source="category.id", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = RecurringExpense
        fields = (
            "id",
            "branch_id",
            "branch_name",
            "category_id",
            "category_name",
            "expected_amount",
            "frequency",
            "start_date",
            "end_date",
            "due_day",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RecurringExpenseWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    category_id = serializers.UUIDField()
    expected_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    frequency = serializers.ChoiceField(
        choices=RecurringFrequency.choices, default=RecurringFrequency.MONTHLY
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    due_day = serializers.IntegerField(min_value=1, max_value=28, default=1)
    description = serializers.CharField(required=False, allow_blank=True, max_length=500)
    is_active = serializers.BooleanField(required=False, default=True)


class ExpenseSerializer(serializers.ModelSerializer):
    branch_id = serializers.UUIDField(source="branch.id", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    category_id = serializers.UUIDField(source="category.id", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    submitted_by_email = serializers.EmailField(source="submitted_by.email", read_only=True, default="")
    submitted_by_name = serializers.CharField(
        source="submitted_by.full_name", read_only=True, default=""
    )
    approved_by_email = serializers.EmailField(source="approved_by.email", read_only=True, default="")
    receipt_url = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = (
            "id",
            "branch_id",
            "branch_name",
            "category_id",
            "category_name",
            "entry_type",
            "status",
            "amount",
            "expense_date",
            "billing_period",
            "payment_method",
            "description",
            "receipt_url",
            "submitted_by_email",
            "submitted_by_name",
            "submitted_at",
            "approved_by_email",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "paid_at",
            "payment_reference",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_receipt_url(self, obj) -> str | None:
        if not obj.receipt:
            return None
        request = self.context.get("request")
        url = obj.receipt.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class ExpenseWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    category_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    expense_date = serializers.DateField()
    billing_period = serializers.RegexField(
        r"^\d{4}-\d{2}$", required=False, allow_blank=True, default=""
    )
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.OTHER)
    description = serializers.CharField(required=False, allow_blank=True)
    receipt = serializers.FileField(required=False, allow_null=True)


class ExpenseRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


class ExpensePaySerializer(serializers.Serializer):
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=120)


class ExpenseSummarySerializer(serializers.Serializer):
    pending_approval = serializers.IntegerField()
    draft = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    paid = serializers.IntegerField()
    total_pending_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class ExpenseReportRowSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    branch_name = serializers.CharField()
    status = serializers.ChoiceField(choices=ExpenseStatus.choices)
    count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
