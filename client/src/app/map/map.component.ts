import { Component, AfterViewInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpClient, HttpParams } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { Subject, of } from 'rxjs';
import { debounceTime, distinctUntilChanged, switchMap } from 'rxjs/operators';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import * as L from 'leaflet';

import type { NatureReserveDetail, NatureReserveListItem, ReserveGeometry } from './reserve-detail';
import { PROTECTION_LEVEL_OPTIONS, protectionLevelFromProtectClass } from './protection-class';
import { ReservePickerComponent } from './reserve-picker/reserve-picker.component';
import { ReserveSidebarComponent } from './reserve-sidebar/reserve-sidebar.component';
import { environment } from '../../environments/environment';

const DEFAULT_CENTER: L.LatLngTuple = [52.0907, 5.1214];
const DEFAULT_ZOOM = 11;
const DEFAULT_MAX_NATIVE_ZOOM = 13;
const API_BASE = '/api';
const VECTOR_TILE_URL = environment.vectorTileUrl;

interface AppConfig {
  vector_tile_max_zoom: number;
}

const RESERVE_LAYER_STYLE: L.PathOptions = {
  fill: true,
  fillColor: '#2e7d32',
  fillOpacity: 0.3,
  stroke: true,
  color: '#2e7d32',
  weight: 2,
  opacity: 0.8,
};

const HIGHLIGHT_LAYER_STYLE: L.PathOptions = {
  fill: true,
  fillColor: '#ed6c02',
  fillOpacity: 0.25,
  stroke: true,
  color: '#ed6c02',
  weight: 3,
  opacity: 1,
};

function geometryToLatLngBounds(geometry: ReserveGeometry): L.LatLngBounds | null {
  const coords: L.LatLngTuple[] = [];
  if (geometry.type === 'Polygon') {
    for (const ring of geometry.coordinates) {
      for (const pt of ring) {
        if (pt.length >= 2) coords.push([pt[1], pt[0]]);
      }
    }
  } else if (geometry.type === 'MultiPolygon') {
    for (const poly of geometry.coordinates) {
      for (const ring of poly) {
        for (const pt of ring) {
          if (pt.length >= 2) coords.push([pt[1], pt[0]]);
        }
      }
    }
  }
  if (coords.length === 0) return null;
  return L.latLngBounds(coords);
}

export interface OperatorOption {
  id: number;
  name: string;
  reserve_count: number;
}

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatToolbarModule,
    MatFormFieldModule,
    MatSelectModule,
    MatInputModule,
    MatIconModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    ReservePickerComponent,
    ReserveSidebarComponent,
  ],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css',
})
export class MapComponent implements AfterViewInit, OnDestroy {
  private map: L.Map | null = null;
  private vectorTileLayer: L.Layer | null = null;
  private highlightLayer: L.Layer | null = null;
  private searchInput$ = new Subject<string>();
  private maxNativeZoom = DEFAULT_MAX_NATIVE_ZOOM;

  protected operators: OperatorOption[] = [];
  protected protectionLevelOptions = PROTECTION_LEVEL_OPTIONS;
  protected selectedProtectionLevel: string | null = null;
  protected selectedOperatorId: number | null = null;
  protected selectedSource: string | null = null;
  protected selectedReserve: NatureReserveDetail | null = null;
  protected sidebarExpanded = false;
  protected loadError: string | null = null;
  protected searchQuery = '';
  protected searchResults: NatureReserveListItem[] = [];
  protected searchLoading = false;
  protected reservesAtPoint: NatureReserveListItem[] = [];
  protected atPointLoading = false;
  protected pickerPosition: { x: number; y: number } | null = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
  ) {
    this.searchInput$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((q) => {
          const trimmed = (q ?? '').trim();
          if (trimmed.length < 2) {
            return of({ results: [] as NatureReserveListItem[] });
          }
          this.searchLoading = true;
          this.cdr.detectChanges();
          const params = new HttpParams().set('search', trimmed).set('page_size', '20');
          return this.http.get<{ results: NatureReserveListItem[] } | NatureReserveListItem[]>(
            `${API_BASE}/nature-reserves/`,
            { params },
          );
        }),
      )
      .subscribe({
        next: (body) => {
          this.searchResults = Array.isArray(body) ? body : (body.results ?? []);
          this.searchLoading = false;
          this.cdr.detectChanges();
        },
        error: () => {
          this.searchLoading = false;
          this.searchResults = [];
          this.cdr.detectChanges();
        },
      });
  }

  ngAfterViewInit(): void {
    this.loadConfig();
    this.loadOperators();
    this.applyProtectionLevelFromUrl();
    this.applyOperatorFromUrl();
    this.applySourceFromUrl();
    this.initMap();
    this.applyReserveFromUrl();
  }

  ngOnDestroy(): void {
    this.removeVectorTileLayer();
    this.removeHighlightLayer();
    if (this.map) {
      this.map.remove();
    }
  }

  protected onProtectionLevelChange(value: string | null): void {
    this.selectedProtectionLevel = value;
    this.updateVectorTileLayer();
    this.updateUrlFromMap();
  }

  protected onOperatorFilterChange(value: number | null): void {
    this.selectedOperatorId = value;
    this.updateVectorTileLayer();
    this.updateUrlFromMap();
  }

  protected onSourceFilterChange(value: string | null): void {
    this.selectedSource = value;
    this.updateVectorTileLayer();
    this.updateUrlFromMap();
  }

  protected onSearchInput(): void {
    const q = this.searchQuery?.trim() ?? '';
    if (q.length === 0) {
      this.searchResults = [];
      this.cdr.detectChanges();
      return;
    }
    this.searchInput$.next(this.searchQuery!);
  }

  protected selectSearchResult(item: NatureReserveListItem): void {
    this.loadReserve(item.id, true);
    this.searchQuery = '';
    this.searchResults = [];
  }

  protected selectReserveAtPoint(item: NatureReserveListItem): void {
    this.loadReserve(item.id);
    this.reservesAtPoint = [];
    this.pickerPosition = null;
  }

  protected closeReservePicker(): void {
    this.reservesAtPoint = [];
    this.pickerPosition = null;
  }

  private loadConfig(): void {
    this.http.get<AppConfig>(`${API_BASE}/config/`).subscribe({
      next: (config) => {
        this.maxNativeZoom = config.vector_tile_max_zoom ?? DEFAULT_MAX_NATIVE_ZOOM;
        this.updateVectorTileLayer();
      },
    });
  }

  private loadOperators(): void {
    this.http
      .get<OperatorOption[] | { results: OperatorOption[] }>(`${API_BASE}/operators/`)
      .subscribe({
        next: (body) => {
          this.operators = Array.isArray(body) ? body : (body.results ?? []);
          this.cdr.detectChanges();
        },
      });
  }

  private removeVectorTileLayer(): void {
    if (this.map && this.vectorTileLayer) {
      this.map.removeLayer(this.vectorTileLayer);
      this.vectorTileLayer = null;
    }
  }

  private addVectorTileLayer(): void {
    if (!this.map) return;
    const selectedOperatorId = this.selectedOperatorId;
    const selectedProtectionLevel = this.selectedProtectionLevel;
    const selectedSource = this.selectedSource;
    const styleFn = (
      properties: Record<string, unknown>,
      _zoom: number,
    ): L.PathOptions | L.PathOptions[] => {
      const raw = properties?.['operator_ids'];
      const operatorIds = this.parseOperatorIdsFromTile(raw);
      const operatorMatch =
        selectedOperatorId === null ||
        (operatorIds.length > 0 && operatorIds.includes(Number(selectedOperatorId)));
      const rawProtectClass = properties?.['protect_class'];
      const pc =
        typeof rawProtectClass === 'string'
          ? rawProtectClass
          : rawProtectClass != null
            ? String(rawProtectClass)
            : null;
      const level = protectionLevelFromProtectClass(pc);
      const protectionMatch = selectedProtectionLevel === null || level === selectedProtectionLevel;
      const featureSource = properties?.['source'];
      const sourceMatch = selectedSource === null || featureSource === selectedSource;
      const show = operatorMatch && protectionMatch && sourceMatch;
      return show ? RESERVE_LAYER_STYLE : [];
    };
    const windowL = (window as unknown as { L: typeof L }).L;
    const layer = (
      windowL as unknown as { vectorGrid: { protobuf: (url: string, opts: object) => L.Layer } }
    ).vectorGrid.protobuf(VECTOR_TILE_URL, {
      vectorTileLayerStyles: {
        nature_reserves: styleFn,
      },
      interactive: true,
      maxNativeZoom: this.maxNativeZoom,
      getFeatureId: (f: { properties: { id?: string; osm_id?: string } }) =>
        f.properties.id ?? String(f.properties.osm_id ?? ''),
    });
    layer.on('click', (e: L.LeafletMouseEvent) => this.onVectorTileClick(e));
    layer.addTo(this.map);
    this.vectorTileLayer = layer;
  }

  private parseOperatorIdsFromTile(raw: unknown): number[] {
    if (raw == null) return [];
    if (Array.isArray(raw)) {
      return raw.map((v) => Number(v)).filter((n) => !Number.isNaN(n));
    }
    if (typeof raw === 'string') {
      const trimmed = raw.trim();
      if (trimmed === '') return [];
      if (trimmed.startsWith('[')) {
        try {
          const arr = JSON.parse(trimmed) as unknown[];
          return Array.isArray(arr)
            ? arr.map((v) => Number(v)).filter((n) => !Number.isNaN(n))
            : [];
        } catch {
          return [];
        }
      }
      return trimmed
        .split(',')
        .map((s) => Number(s.trim()))
        .filter((n) => !Number.isNaN(n));
    }
    return [];
  }

  private updateVectorTileLayer(): void {
    this.removeVectorTileLayer();
    this.addVectorTileLayer();
    if (this.highlightLayer && this.map && 'bringToFront' in this.highlightLayer) {
      (this.highlightLayer as { bringToFront: () => void }).bringToFront();
    }
  }

  /**
   * On vector tile click we call the at_point API because Leaflet.VectorGrid only
   * exposes one feature per click (e.layer). It has no API to get "all features at
   * this point", so we need the backend to detect multiple reserves and show the
   * picker. The single clicked feature id is used as fallback when at_point
   * returns no results (fallbackReserveFromTileClick).
   */
  private onVectorTileClick(e: L.LeafletMouseEvent): void {
    this.reservesAtPoint = [];
    this.pickerPosition = this.map ? this.map.latLngToContainerPoint(e.latlng) : null;
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    this.atPointLoading = true;
    this.cdr.detectChanges();
    const params = new HttpParams().set('lat', String(lat)).set('lon', String(lng));
    this.http
      .get<NatureReserveListItem[]>(`${API_BASE}/nature-reserves/at_point/`, { params })
      .subscribe({
        next: (reserves) => {
          this.atPointLoading = false;
          if (reserves.length === 0) {
            this.fallbackReserveFromTileClick(e);
          } else if (reserves.length === 1) {
            this.loadReserve(reserves[0].id);
          } else {
            this.reservesAtPoint = reserves;
          }
          this.cdr.detectChanges();
        },
        error: () => {
          this.atPointLoading = false;
          this.fallbackReserveFromTileClick(e);
          this.cdr.detectChanges();
        },
      });
  }

  private fallbackReserveFromTileClick(e: L.LeafletMouseEvent): void {
    const ev = e as L.LeafletMouseEvent & { layer?: { properties?: Record<string, unknown> } };
    const props =
      ev.layer?.properties ??
      (e as unknown as { target?: { properties?: Record<string, unknown> } }).target?.properties;
    const rawId = props?.['id'] != null ? String(props['id']) : undefined;
    const osmType = props?.['osm_type'] != null ? String(props['osm_type']) : undefined;
    const id = rawId ? this.normalizeReserveId(rawId, osmType) : undefined;
    if (id) this.loadReserve(id);
  }

  private getInitialMapState(): { center: L.LatLngTuple; zoom: number } {
    const params = this.route.snapshot.queryParamMap;
    const lat = params.get('lat');
    const lng = params.get('lng');
    const zoom = params.get('zoom');
    const center: L.LatLngTuple = [
      lat != null && !Number.isNaN(Number(lat)) ? Number(lat) : DEFAULT_CENTER[0],
      lng != null && !Number.isNaN(Number(lng)) ? Number(lng) : DEFAULT_CENTER[1],
    ];
    const zoomLevel = zoom != null && !Number.isNaN(Number(zoom)) ? Number(zoom) : DEFAULT_ZOOM;
    return { center, zoom: zoomLevel };
  }

  private updateUrlFromMap(): void {
    if (!this.map) return;
    const center = this.map.getCenter();
    const zoom = this.map.getZoom();
    const queryParams: Record<string, string | number | null> = {
      lat: center.lat.toFixed(5),
      lng: center.lng.toFixed(5),
      zoom,
    };
    if (this.selectedReserve) {
      queryParams['reserve'] = this.selectedReserve.id;
    }
    queryParams['protection_level'] = this.selectedProtectionLevel;
    if (this.selectedOperatorId != null) {
      queryParams['operator'] = this.selectedOperatorId;
    } else {
      queryParams['operator'] = null;
    }
    queryParams['source'] = this.selectedSource;
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: queryParams as Record<string, string | number>,
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  private removeHighlightLayer(): void {
    if (this.map && this.highlightLayer) {
      this.map.removeLayer(this.highlightLayer);
      this.highlightLayer = null;
    }
  }

  private updateHighlightLayer(): void {
    this.removeHighlightLayer();
    if (!this.map || !this.selectedReserve?.geometry) return;
    const feature = {
      type: 'Feature' as const,
      geometry: this.selectedReserve.geometry,
      properties: {},
    };
    const layer = L.geoJSON(feature, { style: () => HIGHLIGHT_LAYER_STYLE });
    layer.addTo(this.map);
    if ('bringToFront' in layer) {
      (layer as { bringToFront: () => void }).bringToFront();
    }
    this.highlightLayer = layer;
  }

  private fitMapToReserve(geometry: ReserveGeometry): void {
    if (!this.map) return;
    const bounds = geometryToLatLngBounds(geometry);
    if (bounds) {
      this.map.fitBounds(bounds, { maxZoom: 14, padding: [40, 40] });
    }
  }

  private applyProtectionLevelFromUrl(): void {
    const raw = this.route.snapshot.queryParamMap.get('protection_level');
    if (raw != null && raw !== '') {
      const valid = PROTECTION_LEVEL_OPTIONS.some((o) => o.value === raw);
      if (valid) {
        this.selectedProtectionLevel = raw;
      }
    }
  }

  private applyOperatorFromUrl(): void {
    const raw = this.route.snapshot.queryParamMap.get('operator');
    if (raw != null && raw !== '') {
      const id = Number(raw);
      if (!Number.isNaN(id) && Number.isInteger(id)) {
        this.selectedOperatorId = id;
      }
    }
  }

  private applySourceFromUrl(): void {
    const raw = this.route.snapshot.queryParamMap.get('source');
    if (raw === 'osm' || raw === 'wdpa') {
      this.selectedSource = raw;
    }
  }

  private applyReserveFromUrl(): void {
    const reserveId = this.route.snapshot.queryParamMap.get('reserve');
    if (reserveId) {
      this.loadReserve(reserveId, true);
    }
  }

  private initMap(): void {
    const { center, zoom } = this.getInitialMapState();
    this.map = L.map('map', {
      center,
      zoom,
    });

    this.map.on('moveend', () => this.updateUrlFromMap());

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
    }).addTo(this.map);

    this.addVectorTileLayer();
  }

  private normalizeReserveId(raw: string, osmType?: string): string {
    if (/^(way_|relation_)\d+/.test(raw)) return raw;
    if (/^\d+$/.test(raw)) {
      const prefix = osmType === 'relation' ? 'relation' : 'way';
      return `${prefix}_${raw}`;
    }
    return raw;
  }

  protected loadReserve(id: string, fitMap = false): void {
    this.loadError = null;
    this.http.get<NatureReserveDetail>(`${API_BASE}/nature-reserves/${id}/`).subscribe({
      next: (reserve) => {
        this.selectedReserve = reserve;
        this.sidebarExpanded = true;
        this.updateHighlightLayer();
        if (fitMap && reserve.geometry) {
          this.fitMapToReserve(reserve.geometry);
        }
        this.updateUrlFromMap();
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.loadError = err?.message ?? 'Failed to load reserve';
        this.selectedReserve = null;
        this.sidebarExpanded = true;
        this.cdr.detectChanges();
      },
    });
  }

  protected closeSidebar(): void {
    this.sidebarExpanded = false;
    this.selectedReserve = null;
    this.loadError = null;
    this.reservesAtPoint = [];
    this.pickerPosition = null;
    this.removeHighlightLayer();
    if (this.map) {
      const center = this.map.getCenter();
      const zoom = this.map.getZoom();
      const queryParams: Record<string, string | number | null> = {
        lat: center.lat.toFixed(5),
        lng: center.lng.toFixed(5),
        zoom,
        protection_level: this.selectedProtectionLevel,
        source: this.selectedSource,
      };
      if (this.selectedOperatorId != null) {
        queryParams['operator'] = this.selectedOperatorId;
      }
      this.router.navigate([], {
        relativeTo: this.route,
        queryParams: queryParams as Record<string, string | number>,
        queryParamsHandling: '',
        replaceUrl: true,
      });
    }
  }
}
