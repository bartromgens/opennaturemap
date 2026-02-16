import time
from dataclasses import dataclass

import requests

from django.core.management.base import BaseCommand, CommandError

from api.extractors import OSMNatureReserveExtractor, ServerManager, USER_AGENT

SIMPLE_QUERY = "[out:json][timeout:5];node(1);out;"
SIMPLE_TIMEOUT = 15
# Utrecht region (min_lon, min_lat, max_lon, max_lat) – province/city area
UTRECHT_BBOX: tuple[float, float, float, float] = (4.85, 51.95, 5.55, 52.15)
NATURE_RESERVES_TIMEOUT = 120


@dataclass
class ServerResult:
    url: str
    ok: bool
    duration_sec: float
    status_code: int | None = None
    error: str | None = None
    element_count: int | None = None
    timestamp_osm_base: str | None = None
    raw_response: str | None = None


def test_server(
    url: str, query: str, timeout: int = SIMPLE_TIMEOUT, capture_response: bool = False
) -> ServerResult:
    start = time.perf_counter()
    try:
        response = requests.post(
            url,
            data={"data": query},
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=timeout,
        )
        duration = time.perf_counter() - start

        if response.status_code != 200:
            return ServerResult(
                url=url,
                ok=False,
                duration_sec=duration,
                status_code=response.status_code,
                error=(
                    response.text[:500]
                    if response.text
                    else f"HTTP {response.status_code}"
                ),
                raw_response=response.text if capture_response else None,
            )

        try:
            data = response.json()
        except ValueError as e:
            body = response.text or ""
            content_type = response.headers.get("Content-Type", "")
            preview_len = 400
            preview = (
                body[:preview_len].replace("\n", " ").strip()
                if body
                else "(empty body)"
            )
            suffix = "..." if len(body) > preview_len else ""
            error_detail = (
                f"Invalid JSON: {e}. "
                f"Content-Type: {content_type}. "
                f"Response: {preview}{suffix}"
            )
            return ServerResult(
                url=url,
                ok=False,
                duration_sec=duration,
                status_code=200,
                error=error_detail,
                raw_response=body if capture_response else body[:2000],
            )

        elements = data.get("elements", [])
        osm3s = data.get("osm3s") or {}
        timestamp_osm_base = osm3s.get("timestamp_osm_base")
        return ServerResult(
            url=url,
            ok=True,
            duration_sec=duration,
            status_code=200,
            element_count=len(elements),
            timestamp_osm_base=timestamp_osm_base,
        )
    except requests.exceptions.Timeout:
        duration = time.perf_counter() - start
        return ServerResult(
            url=url,
            ok=False,
            duration_sec=duration,
            error=f"Timeout after {timeout}s",
        )
    except requests.exceptions.RequestException as e:
        duration = time.perf_counter() - start
        return ServerResult(
            url=url,
            ok=False,
            duration_sec=duration,
            error=str(e),
        )


class Command(BaseCommand):
    help = (
        "Test Overpass API servers: send a minimal query to each and report "
        "performance and any errors."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print full server response body for each failure (e.g. HTML error pages).",
        )

    def _run_phase(
        self,
        servers: list[str],
        phase_name: str,
        query: str,
        timeout: int,
        verbose: bool = False,
    ) -> list[ServerResult]:
        results: list[ServerResult] = []
        self.stdout.write(f"{phase_name}\n")
        for url in servers:
            self.stdout.write(f"  {url} ... ", ending="")
            result = test_server(url, query, timeout=timeout, capture_response=verbose)
            results.append(result)
            if result.ok:
                ts = (
                    f" [OSM base: {result.timestamp_osm_base}]"
                    if result.timestamp_osm_base
                    else ""
                )
                self.stdout.write(f"OK ({result.duration_sec:.2f}s){ts}")
            else:
                self.stdout.write(f"FAIL ({result.duration_sec:.2f}s)")
        return results

    def _print_summary(
        self,
        results: list[ServerResult],
        servers: list[str],
        phase_name: str,
        verbose: bool = False,
    ) -> int:
        ok_count = sum(1 for r in results if r.ok)
        self.stdout.write(f"\n{phase_name} — {ok_count}/{len(servers)} OK\n")
        for r in results:
            status = "OK" if r.ok else "ERROR"
            time_str = f"{r.duration_sec:.2f}s"
            extra = ""
            if r.ok:
                parts = []
                if r.element_count is not None:
                    parts.append(f"elements: {r.element_count}")
                if r.timestamp_osm_base:
                    parts.append(f"OSM base: {r.timestamp_osm_base}")
                if parts:
                    extra = f" ({', '.join(parts)})"
            elif r.error:
                err = r.error.replace("\n", " ").strip()
                extra = f" — {err[:450]}{'...' if len(err) > 450 else ''}"
            elif r.status_code:
                extra = f" — HTTP {r.status_code}"
            self.stdout.write(f"  [{status:5}] {time_str:6}  {r.url}{extra}")
            if verbose and r.raw_response and not r.ok:
                self.stdout.write("\n  --- Response body ---")
                self.stdout.write(r.raw_response[:8000])
                self.stdout.write("  ---\n")
        ok_results = [r for r in results if r.ok]
        if ok_results:
            best = min(ok_results, key=lambda r: r.duration_sec)
            self.stdout.write(f"  Fastest: {best.url} ({best.duration_sec:.2f}s)\n")
        return ok_count

    def handle(self, *args, **options):
        servers = ServerManager.DEFAULT_SERVERS
        total_ok = 0
        total_tests = 0

        verbose = options.get("verbose", False)

        results_simple = self._run_phase(
            servers,
            "Testing Overpass API servers (simple query, single node)...\n",
            SIMPLE_QUERY,
            SIMPLE_TIMEOUT,
            verbose=verbose,
        )
        total_tests += len(servers)
        total_ok += sum(1 for r in results_simple if r.ok)

        extractor = OSMNatureReserveExtractor()
        nature_query = extractor.build_query(bbox=UTRECHT_BBOX)
        results_utrecht = self._run_phase(
            servers,
            "\nNature reserves in Utrecht region (bbox)...\n",
            nature_query,
            NATURE_RESERVES_TIMEOUT,
            verbose=verbose,
        )
        total_tests += len(servers)
        total_ok += sum(1 for r in results_utrecht if r.ok)

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 70)

        self._print_summary(
            results_simple, servers, "Simple query (node 1)", verbose=verbose
        )
        self._print_summary(
            results_utrecht, servers, "Nature reserves (Utrecht bbox)", verbose=verbose
        )

        failed = total_tests - total_ok
        if failed:
            raise CommandError(f"{failed} test(s) failed across both phases")
