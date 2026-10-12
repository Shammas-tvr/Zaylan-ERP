from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ExpenseCategoryViewSet,
    ExpenseReportView,
    ExpenseSummaryView,
    ExpenseViewSet,
    RecurringExpenseViewSet,
)

router = DefaultRouter()
router.register("categories", ExpenseCategoryViewSet, basename="expense-categories")
router.register("recurring", RecurringExpenseViewSet, basename="expense-recurring")
router.register("", ExpenseViewSet, basename="expenses")

urlpatterns = [
    path("summary", ExpenseSummaryView.as_view(), name="expense-summary"),
    path("reports/by-branch", ExpenseReportView.as_view(), name="expense-report-by-branch"),
    path("", include(router.urls)),
]
