import {
  Component,
  AfterViewInit,
  OnDestroy,
  ChangeDetectorRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import * as L from 'leaflet';
import 'leaflet.vectorgrid';

import type { NatureReserveDetail } from './reserve-detail';
import { ReserveSidebarComponent } from './reserve-sidebar/reserve-sidebar.component';

const DEFAULT_CENTER: L.LatLngTuple = [52.0907, 5.1214];
const DEFAULT_ZOOM = 11;
const API_BASE = '/api';
const VECTOR_TILE_URL = 'http://localhost:8080/data/nature_reserves/{z}/{x}/{y}.pbf';

const RESERVE_LAYER_STYLE: L.PathOptions = {
  fill: true,
  fillColor: '#2e7d32',
  fillOpacity: 0.3,
  stroke: true,
  color: '#2e7d32',
  weight: 2,
  opacity: 0.8
};

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
    MatToolbarModule,
    MatFormFieldModule,
    MatSelectModule,
    ReserveSidebarComponent
  ],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css'
})
export class MapComponent implements AfterViewInit, OnDestroy {
  private map: L.Map | null = null;
  private vectorTileLayer: L.Layer | null = null;

  protected operators: OperatorOption[] = [];
  protected selectedOperatorId: number | null = null;
  protected selectedReserve: NatureReserveDetail | null = null;
  protected sidebarExpanded = false;
  protected loadError: string | null = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngAfterViewInit(): void {
    this.loadOperators();
    this.initMap();
  }

  ngOnDestroy(): void {
    this.removeVectorTileLayer();
    if (this.map) {
      this.map.remove();
    }
  }

  protected onOperatorFilterChange(value: number | null): void {
    this.selectedOperatorId = value;
    this.updateVectorTileLayer();
  }

  private loadOperators(): void {
    this.http.get<OperatorOption[] | { results: OperatorOption[] }>(`${API_BASE}/operators/`).subscribe({
      next: (body) => {
        this.operators = Array.isArray(body) ? body : (body.results ?? []);
        this.cdr.detectChanges();
      }
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
    const selectedId = this.selectedOperatorId;
    const styleFn = (properties: Record<string, unknown>, _zoom: number): L.PathOptions | L.PathOptions[] => {
      const raw = properties?.['operator_ids'];
      const operatorIds = this.parseOperatorIdsFromTile(raw);
      const show =
        selectedId === null ||
        (operatorIds.length > 0 && operatorIds.includes(Number(selectedId)));
      return show ? RESERVE_LAYER_STYLE : [];
    };
    const layer = (L as unknown as { vectorGrid: { protobuf: (url: string, opts: object) => L.Layer } }).vectorGrid.protobuf(
      VECTOR_TILE_URL,
      {
        vectorTileLayerStyles: {
          nature_reserves: styleFn
        },
        interactive: true,
        getFeatureId: (f: { properties: { id?: string; osm_id?: string } }) =>
          f.properties.id ?? String(f.properties.osm_id ?? '')
      }
    );
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
  }

  private onVectorTileClick(e: L.LeafletMouseEvent): void {
    const ev = e as L.LeafletMouseEvent & { layer?: { properties?: Record<string, unknown> } };
    const props = ev.layer?.properties ?? (e as unknown as { target?: { properties?: Record<string, unknown> } }).target?.properties;
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
      lng != null && !Number.isNaN(Number(lng)) ? Number(lng) : DEFAULT_CENTER[1]
    ];
    const zoomLevel =
      zoom != null && !Number.isNaN(Number(zoom)) ? Number(zoom) : DEFAULT_ZOOM;
    return { center, zoom: zoomLevel };
  }

  private updateUrlFromMap(): void {
    if (!this.map) return;
    const center = this.map.getCenter();
    const zoom = this.map.getZoom();
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {
        lat: center.lat.toFixed(5),
        lng: center.lng.toFixed(5),
        zoom
      },
      queryParamsHandling: 'merge',
      replaceUrl: true
    });
  }

  private initMap(): void {
    const { center, zoom } = this.getInitialMapState();
    this.map = L.map('map', {
      center,
      zoom
    });

    this.map.on('moveend', () => this.updateUrlFromMap());

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
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

  protected loadReserve(id: string): void {
    console.log('[map] loadReserve', id);
    this.loadError = null;
    this.http.get<NatureReserveDetail>(`${API_BASE}/nature-reserves/${id}/`).subscribe({
      next: (reserve) => {
        console.log('[map] reserve loaded', reserve);
        this.selectedReserve = reserve;
        this.sidebarExpanded = true;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.log('[map] reserve load error', err);
        this.loadError = err?.message ?? 'Failed to load reserve';
        this.selectedReserve = null;
        this.sidebarExpanded = true;
        this.cdr.detectChanges();
      }
    });
  }

  protected closeSidebar(): void {
    this.sidebarExpanded = false;
    this.selectedReserve = null;
    this.loadError = null;
  }
}
