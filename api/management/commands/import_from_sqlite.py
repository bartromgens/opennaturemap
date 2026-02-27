import json
import sqlite3
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import NatureReserve, Operator


class Command(BaseCommand):
    help = (
        "Import nature reserves, operators, and their M2M relationships "
        "from a SQLite database into the default (PostgreSQL) database."
    )

    DEFAULT_BATCH_SIZE = 1000

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--db",
            default=None,
            metavar="PATH",
            help="Path to the SQLite database file (default: db.sqlite3 in project root).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=self.DEFAULT_BATCH_SIZE,
            metavar="N",
            help=f"Number of rows per bulk insert (default: {self.DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing reserves, operators, and M2M links before importing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        db_path = Path(options["db"] or settings.BASE_DIR / "db.sqlite3")
        batch_size: int = options["batch_size"]

        if not db_path.exists():
            self.stdout.write(self.style.ERROR(f"SQLite file not found: {db_path}"))
            return

        self.stdout.write(f"Source: {db_path}")
        self.stdout.write(f"Batch size: {batch_size}")

        if options["clear"]:
            nr_count = NatureReserve.objects.count()
            op_count = Operator.objects.count()
            NatureReserve.objects.all().delete()
            Operator.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Cleared {nr_count} nature reserve(s) and {op_count} operator(s)."
                )
            )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            self._import_operators(conn, batch_size)
            self._import_nature_reserves(conn, batch_size)
            self._import_m2m(conn, batch_size)
        finally:
            conn.close()

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete. "
                f"Database now contains {NatureReserve.objects.count()} reserve(s) "
                f"and {Operator.objects.count()} operator(s)."
            )
        )

    def _import_operators(self, conn: sqlite3.Connection, batch_size: int) -> None:
        self.stdout.write("Importing operators...")
        rows = conn.execute("SELECT id, name FROM operators ORDER BY id").fetchall()
        total = len(rows)
        if total == 0:
            self.stdout.write("  No operators found.")
            return

        created = updated = 0
        for start in range(0, total, batch_size):
            chunk = rows[start : start + batch_size]
            objs = [Operator(id=row["id"], name=row["name"]) for row in chunk]
            results = Operator.objects.bulk_create(
                objs,
                update_conflicts=True,
                unique_fields=["name"],
                update_fields=["name"],
            )
            for obj in results:
                if obj._state.adding:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            f"  Operators: {total} total, {created} created, {updated} updated."
        )

    def _import_nature_reserves(
        self, conn: sqlite3.Connection, batch_size: int
    ) -> None:
        self.stdout.write("Importing nature reserves...")
        rows = conn.execute(
            "SELECT id, name, osm_data, geojson, tags, area_type, protect_class, "
            "min_lat, max_lat, min_lon, max_lon, created_at, updated_at "
            "FROM nature_reserves ORDER BY id"
        ).fetchall()
        total = len(rows)
        if total == 0:
            self.stdout.write("  No nature reserves found.")
            return

        NatureReserve._meta.get_field("created_at").auto_now_add = False
        NatureReserve._meta.get_field("updated_at").auto_now = False
        try:
            created = updated = 0
            for start in range(0, total, batch_size):
                chunk = rows[start : start + batch_size]
                objs = [
                    NatureReserve(
                        id=row["id"],
                        name=row["name"],
                        osm_data=json.loads(row["osm_data"]) if row["osm_data"] else {},
                        geojson=json.loads(row["geojson"]) if row["geojson"] else None,
                        tags=json.loads(row["tags"]) if row["tags"] else {},
                        area_type=row["area_type"],
                        protect_class=row["protect_class"],
                        min_lat=row["min_lat"],
                        max_lat=row["max_lat"],
                        min_lon=row["min_lon"],
                        max_lon=row["max_lon"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                    for row in chunk
                ]
                results = NatureReserve.objects.bulk_create(
                    objs,
                    update_conflicts=True,
                    unique_fields=["id"],
                    update_fields=[
                        "name",
                        "osm_data",
                        "geojson",
                        "tags",
                        "area_type",
                        "protect_class",
                        "min_lat",
                        "max_lat",
                        "min_lon",
                        "max_lon",
                        "updated_at",
                    ],
                )
                for obj in results:
                    if obj._state.adding:
                        created += 1
                    else:
                        updated += 1

                if (start + batch_size) % (batch_size * 10) == 0 or (
                    start + batch_size
                ) >= total:
                    self.stdout.write(
                        f"  Processed {min(start + batch_size, total)}/{total}..."
                    )
        finally:
            NatureReserve._meta.get_field("created_at").auto_now_add = True
            NatureReserve._meta.get_field("updated_at").auto_now = True

        self.stdout.write(
            f"  Nature reserves: {total} total, {created} created, {updated} updated."
        )

    def _import_m2m(self, conn: sqlite3.Connection, batch_size: int) -> None:
        self.stdout.write("Importing operator links...")
        rows = conn.execute(
            "SELECT naturereserve_id, operator_id FROM nature_reserves_operators "
            "ORDER BY naturereserve_id, operator_id"
        ).fetchall()
        total = len(rows)
        if total == 0:
            self.stdout.write("  No operator links found.")
            return

        Through = NatureReserve.operators.through
        inserted = 0
        for start in range(0, total, batch_size):
            chunk = rows[start : start + batch_size]
            objs = [
                Through(
                    naturereserve_id=row["naturereserve_id"],
                    operator_id=row["operator_id"],
                )
                for row in chunk
            ]
            results = Through.objects.bulk_create(objs, ignore_conflicts=True)
            inserted += len(results)

        self.stdout.write(f"  Operator links: {total} total, {inserted} inserted.")
