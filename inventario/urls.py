from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import  LoginView, ProductoViewSet, UserDataView, UsuarioViewSet, FacturaViewSet, IngresoProductoViewSet

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet)
router.register(r'productos', ProductoViewSet)
router.register(r'facturas', FacturaViewSet)
router.register(r'ingreso', IngresoProductoViewSet)



urlpatterns = [
    # Autenticación
   
    path('auth/login/', LoginView.as_view(), name='api_login'),
    path('auth/me/', UserDataView.as_view(), name='user_data'), # Maneja el GET del dashboard
    path('', include(router.urls)),  # CRUD de usuarios    
]
