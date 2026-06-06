from django.contrib import admin
from django.contrib.sitemaps.views import index as sitemap_index, sitemap
from django.urls import path, include

from api.sitemaps import sitemaps

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path(
        "sitemap.xml",
        sitemap_index,
        {"sitemaps": sitemaps, "sitemap_url_name": "sitemaps"},
        name="sitemap-index",
    ),
    path(
        "sitemap-<section>.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="sitemaps",
    ),
]
