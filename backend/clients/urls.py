from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, PlanViewSet


router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'plans', PlanViewSet, basename='plan')

urlpatterns = [
    path('', include(router.urls)),
    
]