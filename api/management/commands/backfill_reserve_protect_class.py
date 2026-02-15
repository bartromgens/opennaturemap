from django.core.management.base import BaseCommand

from api.models import NatureReserve


def protect_class_from_tags(tags: dict) -> str | None:
    value = (tags.get("protect_class") or "").strip()
    return value if value else None


class Command(BaseCommand):
    help = (
        "Set protect_class from reserve tags (OSM protect_class) for reserves "
        "missing it or when --force is used."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be updated, do not save.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute protect_class for all reserves from tags.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        if force:
            reserves = NatureReserve.objects.all()
            total = reserves.count()
            if total == 0:
                self.stdout.write("No reserves in database.")
                return
            self.stdout.write(f"Processing all {total} reserve(s).")
        else:
            reserves = NatureReserve.objects.filter(protect_class__isnull=True)
            total = reserves.count()
            if total == 0:
                self.stdout.write("No reserves with missing protect_class.")
                return
            self.stdout.write(f"Found {total} reserve(s) with missing protect_class.")
        if dry_run:
            self.stdout.write("Dry run: no changes written.")
        updated = 0
        set_count = 0
        cleared_count = 0
        for reserve in reserves:
            new_value = protect_class_from_tags(reserve.tags or {})
            if force and new_value == reserve.protect_class:
                continue
            if not dry_run:
                reserve.protect_class = new_value
                reserve.save(update_fields=["protect_class"])
            updated += 1
            if new_value:
                set_count += 1
            else:
                cleared_count += 1
        msg = f"Processed {updated} reserve(s)"
        if set_count:
            msg += f", {set_count} set"
        if cleared_count:
            msg += f", {cleared_count} cleared (no protect_class in tags)"
        msg += "."
        self.stdout.write(msg)
