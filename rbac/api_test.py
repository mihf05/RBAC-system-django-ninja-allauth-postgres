"""
Real REST API endpoints for testing RBAC permissions dynamically.
Includes endpoints for Articles (full CRUD) and Settings (Read and Update only).
"""
from ninja import Router
from ninja.errors import HttpError
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from .models import Article
from .permissions import require_permission
from .schemas import (
    ArticleCreateSchema, ArticleResponseSchema,
    MessageSchema,
)

User = get_user_model()

test_router = Router()

# ══════════════════════════════════════════════════════════════════════
# ARTICLES API (Fully CRUD - read, write, update, delete)
# ══════════════════════════════════════════════════════════════════════

@test_router.get("/articles/", response=list[ArticleResponseSchema])
def test_list_articles(request):
    """
    List all articles.
    Requires Read permission on "Articles".
    """
    require_permission(request, "Articles", "read")
    
    articles = Article.objects.select_related('author').all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "author_email": a.author.email,
            "created_at": a.created_at,
        }
        for a in articles
    ]


@test_router.post("/articles/", response={201: ArticleResponseSchema, 400: MessageSchema})
def test_create_article(request, payload: ArticleCreateSchema):
    """
    Create a new article.
    Requires Write permission on "Articles".
    """
    user = require_permission(request, "Articles", "write")
    
    if not payload.title.strip():
        raise HttpError(400, "Title is required")
        
    article = Article.objects.create(
        title=payload.title.strip(),
        content=payload.content,
        author=user,
    )
    
    return 201, {
        "id": article.id,
        "title": article.title,
        "content": article.content,
        "author_email": article.author.email,
        "created_at": article.created_at,
    }


@test_router.put("/articles/{article_id}/", response={200: ArticleResponseSchema, 400: MessageSchema, 404: MessageSchema})
def test_update_article(request, article_id: int, payload: ArticleCreateSchema):
    """
    Update an article.
    Requires Update permission on "Articles".
    """
    require_permission(request, "Articles", "update")
    
    article = get_object_or_404(Article, id=article_id)
    
    if not payload.title.strip():
        raise HttpError(400, "Title is required")
        
    article.title = payload.title.strip()
    article.content = payload.content
    article.save()
    
    return 200, {
        "id": article.id,
        "title": article.title,
        "content": article.content,
        "author_email": article.author.email,
        "created_at": article.created_at,
    }


@test_router.delete("/articles/{article_id}/", response={200: MessageSchema, 404: MessageSchema})
def test_delete_article(request, article_id: int):
    """
    Delete an article.
    Requires Delete permission on "Articles".
    """
    require_permission(request, "Articles", "delete")
    
    article = get_object_or_404(Article, id=article_id)
    title = article.title
    article.delete()
    
    return 200, {"message": f"Article '{title}' deleted successfully"}


# ══════════════════════════════════════════════════════════════════════
# SYSTEM SETTINGS API (Read and Update only - matching database constraints!)
# ══════════════════════════════════════════════════════════════════════

# Mock in-memory/DB setting representation
MOCK_SETTINGS = {
    "site_name": "Antigravity Premium LMS",
    "maintenance_mode": False,
    "allowed_file_types": "pdf,doc,docx,png,jpg",
    "token_expiry_minutes": 5,
}

@test_router.get("/settings/", response=dict)
def test_get_settings(request):
    """
    Get system settings.
    Requires Read permission on "Settings".
    """
    require_permission(request, "Settings", "read")
    return MOCK_SETTINGS


@test_router.put("/settings/", response={200: dict, 400: MessageSchema})
def test_update_settings(request, payload: dict):
    """
    Update system settings.
    Requires Update permission on "Settings".
    """
    require_permission(request, "Settings", "update")
    
    global MOCK_SETTINGS
    for key in MOCK_SETTINGS:
        if key in payload:
            MOCK_SETTINGS[key] = payload[key]
            
    return 200, MOCK_SETTINGS


# ══════════════════════════════════════════════════════════════════════
# DYNAMIC SIMULATION API (Tests ANY resource/operation dynamically!)
# ══════════════════════════════════════════════════════════════════════

@test_router.get("/request/", response={200: dict, 400: MessageSchema, 403: MessageSchema})
def dynamic_test_request(request, resource: str, action: str):
    """
    Simulate a secure live request for any system feature/API.
    Accepts ?resource=Articles&action=read
    Checks dynamic permission against active user roles.
    """
    action = action.strip().lower()
    if action not in ['read', 'write', 'update', 'delete']:
        raise HttpError(400, "Invalid operation. Must be read, write, update, or delete.")

    # Enforce permissions dynamically
    require_permission(request, resource, action)

    return 200, {
        "status": "Request Authorized",
        "resource": resource,
        "operation": action,
        "compliance_status": "COMPLIANT",
        "details": f"User is fully authorized to perform '{action}' on resource '{resource}'."
    }
