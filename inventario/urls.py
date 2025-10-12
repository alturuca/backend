from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import  LoginView, UserDataView, UsuarioViewSet

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet)

urlpatterns = [
    # Autenticación
   
    path('auth/login/', LoginView.as_view(), name='api_login'),
    path('auth/me/', UserDataView.as_view(), name='user_data'), # Maneja el GET del dashboard
    path('', include(router.urls)),  # CRUD de usuarios    
]
