from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NatureReserveViewSet, OperatorViewSet

router = DefaultRouter()
router.register(r"nature-reserves", NatureReserveViewSet, basename="nature-reserve")
router.register(r"operators", OperatorViewSet, basename="operator")

urlpatterns = [
    path("", include(router.urls)),
]
