from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NatureReserveViewSet

router = DefaultRouter()
router.register(r"nature-reserves", NatureReserveViewSet, basename="nature-reserve")

urlpatterns = [
    path("", include(router.urls)),
]
