from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='demo-index'),
    path('callback/', views.callback, name='demo-callback'),
    path('logout/', views.logout_view, name='demo-logout'),
]
