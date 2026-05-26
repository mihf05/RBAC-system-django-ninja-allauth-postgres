"""
Django Ninja API configuration.
Central router that combines all API endpoints.
"""
from ninja import NinjaAPI
from ninja.errors import ValidationError, HttpError
from django.http import JsonResponse

from accounts.api import router as auth_router
from rbac.api import (
    roles_router,
    resources_router,
    users_router,
    stats_router,
    activity_router,
)

api = NinjaAPI(
    title="RBAC API",
    version="1.0.0",
    description="Role-Based Access Control System API",
    urls_namespace="api",
)

# Register routers
api.add_router("/auth/", auth_router, tags=["Authentication"])
api.add_router("/roles/", roles_router, tags=["Roles"])
api.add_router("/resources/", resources_router, tags=["Resources"])
api.add_router("/users/", users_router, tags=["Users"])
api.add_router("/stats/", stats_router, tags=["Statistics"])
api.add_router("/activity/", activity_router, tags=["Activity Log"])


@api.exception_handler(ValidationError)
def validation_error_handler(request, exc):
    return JsonResponse(
        {"detail": "Validation error", "errors": exc.errors},
        status=422,
    )


@api.exception_handler(HttpError)
def http_error_handler(request, exc):
    return JsonResponse({"detail": str(exc)}, status=exc.status_code)
