from fastapi import APIRouter

from zylora_api.api.admin_auth import router as admin_auth_router
from zylora_api.api.admin_exports import router as admin_exports_router
from zylora_api.api.admin_leads import router as admin_leads_router
from zylora_api.api.admin_operations import router as admin_operations_router
from zylora_api.api.ai_builder import router as ai_builder_router
from zylora_api.api.analytics import router as analytics_router
from zylora_api.api.auth import router as auth_router
from zylora_api.api.blog import router as blog_router
from zylora_api.api.campaigns import router as campaigns_router
from zylora_api.api.commerce import router as commerce_router
from zylora_api.api.contact import router as contact_router
from zylora_api.api.editor import router as editor_router
from zylora_api.api.health import router as health_router
from zylora_api.api.knowledge import router as knowledge_router
from zylora_api.api.leads import router as leads_router
from zylora_api.api.public import router as public_router
from zylora_api.api.publishing import router as publishing_router
from zylora_api.api.templates import router as templates_router
from zylora_api.api.twilio_webhooks import router as twilio_webhooks_router
from zylora_api.api.websites import router as websites_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(blog_router)
api_router.include_router(campaigns_router)
api_router.include_router(commerce_router)
api_router.include_router(contact_router)
api_router.include_router(analytics_router)
api_router.include_router(ai_builder_router)
api_router.include_router(editor_router)
api_router.include_router(leads_router)
api_router.include_router(knowledge_router)
api_router.include_router(publishing_router)
api_router.include_router(public_router)
api_router.include_router(admin_auth_router)
api_router.include_router(admin_exports_router)
api_router.include_router(admin_leads_router)
api_router.include_router(admin_operations_router)
api_router.include_router(templates_router)
api_router.include_router(twilio_webhooks_router)
api_router.include_router(websites_router)
