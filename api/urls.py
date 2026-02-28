from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NatureReserveViewSet, OperatorViewSet, config_view

router = DefaultRouter()
router.register(r"nature-reserves", NatureReserveViewSet, basename="nature-reserve")
router.register(r"operators", OperatorViewSet, basename="operator")

urlpatterns = [
    path("config/", config_view, name="config"),
    path("", include(router.urls)),
]
