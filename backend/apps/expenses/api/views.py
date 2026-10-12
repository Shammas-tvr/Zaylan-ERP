from django.db.models import Count, Sum
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.api.base import TenantAPIView, TenantScopedViewSet

from .. import services
from ..models import Expense, ExpenseCategory, ExpenseStatus, RecurringExpense
from .serializers import (
    ExpenseCategorySerializer,
    ExpenseCategoryWriteSerializer,
    ExpensePaySerializer,
    ExpenseRejectSerializer,
    ExpenseReportRowSerializer,
    ExpenseSerializer,
    ExpenseSummarySerializer,
    ExpenseWriteSerializer,
    RecurringExpenseSerializer,
    RecurringExpenseWriteSerializer,
)


class ExpenseCategoryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    TenantScopedViewSet,
):
    serializer_class = ExpenseCategorySerializer
    queryset = ExpenseCategory.objects.all()
    required_feature = "expenses"
    permission_rules = {
        "list": "expenses.view",
        "retrieve": "expenses.view",
        "create": "expenses.configure",
        "partial_update": "expenses.configure",
    }
    search_fields = ("code", "name")
    filterset_fields = ("is_active",)
    ordering_fields = ("name", "code", "created_at")

    @extend_schema(request=ExpenseCategoryWriteSerializer, responses={201: ExpenseCategorySerializer})
    def create(self, request):
        serializer = ExpenseCategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = services.create_category(
            request.tenant, serializer.validated_data, request=request
        )
        return Response(ExpenseCategorySerializer(category).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ExpenseCategoryWriteSerializer, responses=ExpenseCategorySerializer)
    def partial_update(self, request, pk=None):
        category = self.get_object()
        serializer = ExpenseCategoryWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = services.update_category(
            request.tenant, category, serializer.validated_data, request=request
        )
        return Response(ExpenseCategorySerializer(category).data)


class RecurringExpenseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    TenantScopedViewSet,
):
    serializer_class = RecurringExpenseSerializer
    queryset = RecurringExpense.objects.select_related("branch", "category")
    required_feature = "expenses"
    permission_rules = {
        "list": "expenses.configure",
        "retrieve": "expenses.configure",
        "create": "expenses.configure",
        "partial_update": "expenses.configure",
    }
    filterset_fields = ("is_active", "branch", "category")
    ordering_fields = ("created_at", "start_date")

    @extend_schema(request=RecurringExpenseWriteSerializer, responses={201: RecurringExpenseSerializer})
    def create(self, request):
        serializer = RecurringExpenseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = services.create_recurring(request.tenant, serializer.validated_data, request=request)
        return Response(RecurringExpenseSerializer(row).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=RecurringExpenseWriteSerializer, responses=RecurringExpenseSerializer)
    def partial_update(self, request, pk=None):
        row = self.get_object()
        serializer = RecurringExpenseWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = services.update_recurring(
            request.tenant, row, serializer.validated_data, request=request
        )
        return Response(RecurringExpenseSerializer(row).data)


class ExpenseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    TenantScopedViewSet,
):
    serializer_class = ExpenseSerializer
    queryset = Expense.objects.select_related(
        "branch", "category", "submitted_by", "approved_by", "rejected_by", "paid_by"
    )
    required_feature = "expenses"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_rules = {
        "list": "expenses.view",
        "retrieve": "expenses.view",
        "create": "expenses.submit",
        "partial_update": "expenses.submit",
        "submit": "expenses.submit",
        "approve": "expenses.approve",
        "reject": "expenses.approve",
        "mark_paid": "expenses.pay",
    }
    branch_scoped_actions = ("list", "retrieve", "create", "partial_update", "submit")
    search_fields = ("description", "billing_period", "category__name", "branch__name")
    filterset_fields = ("status", "entry_type", "branch", "category", "billing_period")
    ordering_fields = ("expense_date", "created_at", "amount", "status")

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in self.branch_scoped_actions:
            code = self.permission_rules.get(self.action, "expenses.view")
            # Approvers with tenant-wide view see all; branch users only their branches.
            if code in self.request.tenant.tenant_permissions:
                return queryset
            return queryset.filter(branch_id__in=self.request.tenant.branch_ids_with(code))
        return queryset

    def get_permission_branch_id(self, expense: Expense):
        return expense.branch_id

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    @extend_schema(request=ExpenseWriteSerializer, responses={201: ExpenseSerializer})
    def create(self, request):
        serializer = ExpenseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = services.create_expense(
            request.tenant, serializer.validated_data, request=request
        )
        return Response(
            ExpenseSerializer(expense, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=ExpenseWriteSerializer, responses=ExpenseSerializer)
    def partial_update(self, request, pk=None):
        expense = self.get_object()
        serializer = ExpenseWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        expense = services.update_draft(
            request.tenant, expense, serializer.validated_data, request=request
        )
        return Response(ExpenseSerializer(expense, context=self.get_serializer_context()).data)

    @extend_schema(responses=ExpenseSerializer)
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        expense = services.submit_expense(request.tenant, self.get_object(), request=request)
        return Response(ExpenseSerializer(expense, context=self.get_serializer_context()).data)

    @extend_schema(responses=ExpenseSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        expense = services.approve_expense(request.tenant, self.get_object(), request=request)
        return Response(ExpenseSerializer(expense, context=self.get_serializer_context()).data)

    @extend_schema(request=ExpenseRejectSerializer, responses=ExpenseSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = ExpenseRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = services.reject_expense(
            request.tenant,
            self.get_object(),
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(ExpenseSerializer(expense, context=self.get_serializer_context()).data)

    @extend_schema(request=ExpensePaySerializer, responses=ExpenseSerializer)
    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        serializer = ExpensePaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = services.mark_paid(
            request.tenant,
            self.get_object(),
            payment_reference=serializer.validated_data.get("payment_reference", ""),
            request=request,
        )
        return Response(ExpenseSerializer(expense, context=self.get_serializer_context()).data)


class ExpenseSummaryView(TenantAPIView):
    required_feature = "expenses"
    permission_rules = {"get": "expenses.view"}

    @extend_schema(responses=ExpenseSummarySerializer)
    def get(self, request):
        qs = Expense.objects.filter(organization=request.tenant.organization)
        if "expenses.view" not in request.tenant.tenant_permissions:
            qs = qs.filter(branch_id__in=request.tenant.branch_ids_with("expenses.view"))
        counts = {row["status"]: row["n"] for row in qs.values("status").annotate(n=Count("pk"))}
        pending_amount = (
            qs.filter(status=ExpenseStatus.PENDING_APPROVAL).aggregate(t=Sum("amount"))["t"] or 0
        )
        return Response(
            {
                "pending_approval": counts.get(ExpenseStatus.PENDING_APPROVAL, 0),
                "draft": counts.get(ExpenseStatus.DRAFT, 0),
                "approved": counts.get(ExpenseStatus.APPROVED, 0),
                "rejected": counts.get(ExpenseStatus.REJECTED, 0),
                "paid": counts.get(ExpenseStatus.PAID, 0),
                "total_pending_amount": pending_amount,
            }
        )


class ExpenseReportView(TenantAPIView):
    required_feature = "expenses"
    permission_rules = {"get": "expenses.view"}

    @extend_schema(responses=ExpenseReportRowSerializer(many=True))
    def get(self, request):
        qs = Expense.objects.filter(organization=request.tenant.organization)
        if "expenses.view" not in request.tenant.tenant_permissions:
            qs = qs.filter(branch_id__in=request.tenant.branch_ids_with("expenses.view"))
        rows = (
            qs.values("branch_id", "branch__name", "status")
            .annotate(count=Count("pk"), total_amount=Sum("amount"))
            .order_by("branch__name", "status")
        )
        return Response(
            [
                {
                    "branch_id": row["branch_id"],
                    "branch_name": row["branch__name"],
                    "status": row["status"],
                    "count": row["count"],
                    "total_amount": row["total_amount"] or 0,
                }
                for row in rows
            ]
        )
