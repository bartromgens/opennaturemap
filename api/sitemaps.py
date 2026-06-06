from django.contrib.sitemaps import Sitemap
from django.db.models import Q

from .models import NatureReserve

SITE_DOMAIN = "opennaturemaps.org"
SITE_PROTOCOL = "https"

QUALITY_SIGNAL_KEYS = ["wikipedia", "website", "contact:website", "url"]


class _BaseSitemap(Sitemap):
    protocol = SITE_PROTOCOL

    def get_domain(self, site=None) -> str:
        return SITE_DOMAIN


class ReserveSitemap(_BaseSitemap):
    changefreq = "monthly"
    priority = 0.6
    limit = 50000

    def items(self):
        quality_filter = Q(tags__has_any_keys=QUALITY_SIGNAL_KEYS)
        return (
            NatureReserve.objects.filter(name__isnull=False)
            .exclude(name="")
            .filter(quality_filter)
            .only("id", "updated_at")
            .order_by("id")
        )

    def location(self, obj: NatureReserve) -> str:
        return f"/reserve/{obj.id}"

    def lastmod(self, obj: NatureReserve):
        return obj.updated_at


class StaticSitemap(_BaseSitemap):
    changefreq = "weekly"

    _pages = [
        ("/", 1.0),
        ("/protection-classes", 0.7),
    ]

    def items(self):
        return self._pages

    def location(self, item) -> str:
        return item[0]

    def priority(self, item) -> float:
        return item[1]


sitemaps = {
    "static": StaticSitemap,
    "reserves": ReserveSitemap,
}
