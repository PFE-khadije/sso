from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, PlanViewSet, OAuthAppByClientIdView


router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'plans', PlanViewSet, basename='plan')

urlpatterns = [
    path('', include(router.urls)),
    path('oauth-apps/<str:oauth_client_id>/', OAuthAppByClientIdView.as_view(), name='oauth-app-detail'),
]
