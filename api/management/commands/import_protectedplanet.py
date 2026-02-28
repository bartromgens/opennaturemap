import io
import zipfile
from pathlib import Path
from typing import Any

import shapefile
from django.core.management.base import BaseCommand, CommandError

from api.models import NatureReserve, Operator

IUCN_TO_PROTECT_CLASS: dict[str, str] = {
    "Ia": "1a",
    "Ib": "1b",
    "II": "2",
    "III": "3",
    "IV": "4",
    "V": "5",
    "VI": "6",
}

IUCN_TO_AREA_TYPE: dict[str, str] = {
    "Ia": "nature_reserve",
    "Ib": "nature_reserve",
    "II": "national_park",
    "III": "nature_monument",
    "IV": "habitat_management",
    "V": "protected_landscape",
    "VI": "sustainable_use",
}

DEFAULT_AREA_TYPE = "protected_area"

SHARD_NAMES = [
    "WDPA_WDOECM_Feb2026_Public_all_shp_0.zip",
    "WDPA_WDOECM_Feb2026_Public_all_shp_1.zip",
    "WDPA_WDOECM_Feb2026_Public_all_shp_2.zip",
]
POLYGON_SHP_SUFFIX = "-polygons.shp"
POINTS_SHP_SUFFIX = "-points.shp"


def _normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _iucn_protect_class(iucn_cat: str) -> str | None:
    return IUCN_TO_PROTECT_CLASS.get(iucn_cat)


def _iucn_area_type(iucn_cat: str) -> str:
    return IUCN_TO_AREA_TYPE.get(iucn_cat, DEFAULT_AREA_TYPE)


def _record_to_props(fields: list[Any], record: list[Any]) -> dict[str, Any]:
    return {fields[i][0]: record[i] for i in range(len(fields))}


def _coords_to_lists(obj: Any) -> Any:
    """Recursively convert tuples to lists so the geometry is JSON-serialisable."""
    if isinstance(obj, (list, tuple)):
        return [_coords_to_lists(item) for item in obj]
    return obj


def _geojson_feature_from_shape(
    shape: Any,
    reserve_id: str,
    name: str | None,
    area_type: str,
    protect_class: str | None,
    tags: dict[str, Any],
    operator_ids: list[int],
) -> dict[str, Any] | None:
    try:
        raw_geom = shape.__geo_interface__
    except (AttributeError, Exception):
        return None
    if not raw_geom or not raw_geom.get("coordinates"):
        return None
    geom = {
        "type": raw_geom["type"],
        "coordinates": _coords_to_lists(raw_geom["coordinates"]),
    }
    props: dict[str, Any] = dict(tags)
    props["id"] = reserve_id
    props["name"] = name or ""
    props["area_type"] = area_type
    props["operator_ids"] = ",".join(str(i) for i in operator_ids)
    if protect_class:
        props["protect_class"] = protect_class
    return {
        "type": "Feature",
        "id": reserve_id,
        "geometry": geom,
        "properties": props,
    }


def _operators_from_mang_auth(mang_auth: str) -> list[Operator]:
    if not mang_auth:
        return []
    result: list[Operator] = []
    for part in mang_auth.split(";"):
        name = part.strip()
        if name and name.lower() not in ("not reported", "not applicable"):
            operator, _ = Operator.objects.get_or_create(name=name)
            result.append(operator)
    return result


def _tags_from_props(props: dict[str, Any]) -> dict[str, Any]:
    keep = {
        "desig": "desig",
        "desig_eng": "DESIG_ENG",
        "desig_type": "DESIG_TYPE",
        "iucn_cat": "IUCN_CAT",
        "iso3": "ISO3",
        "prnt_iso3": "PRNT_ISO3",
        "status": "STATUS",
        "status_yr": "STATUS_YR",
        "mang_auth": "MANG_AUTH",
        "mang_plan": "MANG_PLAN",
        "rep_area": "REP_AREA",
        "gis_area": "GIS_AREA",
        "realm": "REALM",
        "site_type": "SITE_TYPE",
        "gov_type": "GOV_TYPE",
        "own_type": "OWN_TYPE",
        "verif": "VERIF",
        "int_crit": "INT_CRIT",
        "no_take": "NO_TAKE",
        "wdpaid": "SITE_ID",
    }
    tags: dict[str, Any] = {}
    for tag_key, field_key in keep.items():
        val = props.get(field_key)
        if val is not None:
            if isinstance(val, float) and val == int(val):
                val = int(val)
            s = str(val).strip()
            if s and s.lower() not in ("not applicable", "not reported"):
                tags[tag_key] = s
    return tags


class Command(BaseCommand):
    help = "Import nature reserves from Protected Planet / WDPA shapefiles"

    def add_arguments(self, parser):
        parser.add_argument(
            "input_dir",
            type=str,
            help=(
                "Directory containing the WDPA zip files "
                "(WDPA_WDOECM_*_shp_0.zip, _1.zip, _2.zip)"
            ),
        )
        parser.add_argument(
            "--country",
            type=str,
            default=None,
            metavar="ISO3",
            help="Only import reserves for this ISO3 country code (e.g. NLD)",
        )
        parser.add_argument(
            "--shard",
            type=int,
            default=None,
            choices=[0, 1, 2],
            metavar="N",
            help="Only process shard N (0, 1, or 2). Processes all by default.",
        )
        parser.add_argument(
            "--include-points",
            action="store_true",
            help=(
                "Also import point-only reserves (no polygon geometry). "
                "These won't render as areas on the map."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            metavar="N",
            help="Number of records to process before printing progress (default: 500)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database.",
        )

    def handle(self, *args, **options):
        input_dir = Path(options["input_dir"])
        country_filter = (options["country"] or "").strip().upper() or None
        only_shard = options["shard"]
        include_points = options["include_points"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        if not input_dir.is_dir():
            raise CommandError(f"Input directory not found: {input_dir}")

        shards_to_process = [only_shard] if only_shard is not None else [0, 1, 2]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes"))

        total_created = 0
        total_updated = 0
        total_skipped = 0

        for shard_idx in shards_to_process:
            zip_name = SHARD_NAMES[shard_idx]
            zip_path = input_dir / zip_name
            if not zip_path.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Shard {shard_idx} zip not found: {zip_path}, skipping"
                    )
                )
                continue

            self.stdout.write(f"\n{'=' * 60}")
            self.stdout.write(f"Processing shard {shard_idx}: {zip_name}")
            self.stdout.write("=" * 60)

            created, updated, skipped = self._process_shard(
                zip_path,
                shard_idx,
                POLYGON_SHP_SUFFIX,
                country_filter=country_filter,
                batch_size=batch_size,
                dry_run=dry_run,
                is_points=False,
            )
            total_created += created
            total_updated += updated
            total_skipped += skipped

            if include_points:
                self.stdout.write(f"\nProcessing point layer for shard {shard_idx}...")
                created_p, updated_p, skipped_p = self._process_shard(
                    zip_path,
                    shard_idx,
                    POINTS_SHP_SUFFIX,
                    country_filter=country_filter,
                    batch_size=batch_size,
                    dry_run=dry_run,
                    is_points=True,
                )
                total_created += created_p
                total_updated += updated_p
                total_skipped += skipped_p

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Import complete!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"  Created : {total_created}")
        self.stdout.write(f"  Updated : {total_updated}")
        self.stdout.write(f"  Skipped : {total_skipped}")

    def _process_shard(
        self,
        zip_path: Path,
        shard_idx: int,
        shp_suffix: str,
        *,
        country_filter: str | None,
        batch_size: int,
        dry_run: bool,
        is_points: bool,
    ) -> tuple[int, int, int]:
        created_count = 0
        updated_count = 0
        skipped_count = 0

        with zipfile.ZipFile(zip_path) as zf:
            shp_name = next((n for n in zf.namelist() if n.endswith(shp_suffix)), None)
            if shp_name is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  No {shp_suffix} found in {zip_path.name}, skipping"
                    )
                )
                return 0, 0, 0

            base = shp_name[: -len(".shp")]
            required_exts = [".shp", ".dbf", ".shx"]
            missing = [
                f"{base}{ext}"
                for ext in required_exts
                if f"{base}{ext}" not in zf.namelist()
            ]
            if missing:
                raise CommandError(
                    f"Required shapefile components missing in zip: {missing}"
                )

            shp_bytes = zf.read(f"{base}.shp")
            dbf_bytes = zf.read(f"{base}.dbf")
            shx_bytes = zf.read(f"{base}.shx")

        sf = shapefile.Reader(
            shp=io.BytesIO(shp_bytes),
            dbf=io.BytesIO(dbf_bytes),
            shx=io.BytesIO(shx_bytes),
            encoding="utf-8",
        )

        fields = sf.fields[1:]  # skip deletion flag
        total_records = len(sf)
        self.stdout.write(f"  Records in layer: {total_records}")

        for i, shape_rec in enumerate(sf.iterShapeRecords()):
            try:
                props = _record_to_props(fields, shape_rec.record)
                iso3 = _normalize_str(props.get("ISO3"))

                if country_filter and iso3.upper() != country_filter:
                    skipped_count += 1
                    continue

                site_id = str(props.get("SITE_ID", "")).strip()
                if not site_id or site_id == "0":
                    skipped_count += 1
                    continue

                reserve_id = f"wdpa_{site_id}"
                name_eng = _normalize_str(props.get("NAME_ENG"))
                name_local = _normalize_str(props.get("NAME"))
                name = name_eng or name_local or None

                iucn_cat = _normalize_str(props.get("IUCN_CAT"))
                protect_class = _iucn_protect_class(iucn_cat)
                area_type = _iucn_area_type(iucn_cat)

                tags = _tags_from_props(props)

                geojson_features: list[dict[str, Any]] = []
                bbox = None

                operator_list = (
                    []
                    if dry_run
                    else _operators_from_mang_auth(
                        _normalize_str(props.get("MANG_AUTH"))
                    )
                )
                operator_ids = [o.id for o in operator_list]

                if not is_points:
                    # shape.bbox = [min_lon, min_lat, max_lon, max_lat]
                    shp_bbox = shape_rec.shape.bbox
                    if not shp_bbox or len(shp_bbox) < 4:
                        skipped_count += 1
                        continue
                    bbox = (
                        float(shp_bbox[0]),
                        float(shp_bbox[1]),
                        float(shp_bbox[2]),
                        float(shp_bbox[3]),
                    )
                    feature = _geojson_feature_from_shape(
                        shape_rec.shape,
                        reserve_id,
                        name,
                        area_type,
                        protect_class,
                        tags,
                        operator_ids,
                    )
                    if feature:
                        geojson_features = [feature]
                else:
                    try:
                        pt = shape_rec.shape.__geo_interface__
                        coords = pt.get("coordinates") if pt else None
                        if coords and len(coords) >= 2:
                            lon, lat = float(coords[0]), float(coords[1])
                            bbox = (lon, lat, lon, lat)
                        else:
                            skipped_count += 1
                            continue
                    except Exception:
                        skipped_count += 1
                        continue

                if not dry_run:
                    min_lon, min_lat, max_lon, max_lat = bbox
                    # Only touch records with source=wdpa; OSM records are never
                    # overwritten or merged with WDPA data.
                    reserve, created = NatureReserve.objects.update_or_create(
                        id=reserve_id,
                        source=NatureReserve.SOURCE_WDPA,
                        defaults={
                            "name": name,
                            "osm_data": None,
                            "geojson": geojson_features or None,
                            "tags": tags,
                            "area_type": area_type,
                            "protect_class": protect_class,
                            "min_lat": min_lat,
                            "max_lat": max_lat,
                            "min_lon": min_lon,
                            "max_lon": max_lon,
                        },
                    )
                    reserve.operators.set(operator_list)
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                else:
                    created_count += 1

            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  Error at record {i}: {exc}"))
                skipped_count += 1
                continue

            if (i + 1) % batch_size == 0:
                pct = (i + 1) / total_records * 100
                self.stdout.write(
                    f"  {i + 1}/{total_records} ({pct:.1f}%) — "
                    f"created={created_count} updated={updated_count} skipped={skipped_count}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"  Shard {shard_idx} done: "
                f"created={created_count} updated={updated_count} skipped={skipped_count}"
            )
        )
        return created_count, updated_count, skipped_count
