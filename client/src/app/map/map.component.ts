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
import * as L from 'leaflet';
import 'leaflet.vectorgrid';

import type { NatureReserveDetail } from './reserve-detail';
import { ReserveSidebarComponent } from './reserve-sidebar/reserve-sidebar.component';

const DEFAULT_CENTER: L.LatLngTuple = [52.0907, 5.1214];
const DEFAULT_ZOOM = 11;
const API_BASE = '/api';

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [CommonModule, MatToolbarModule, ReserveSidebarComponent],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css'
})
export class MapComponent implements AfterViewInit, OnDestroy {
  private map: L.Map | null = null;

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
    this.initMap();
  }

  ngOnDestroy(): void {
    if (this.map) {
      this.map.remove();
    }
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

    const vectorTileLayer = (L as any).vectorGrid.protobuf(
      'http://localhost:8080/data/nature_reserves/{z}/{x}/{y}.pbf',
      {
        vectorTileLayerStyles: {
          nature_reserves: {
            fill: true,
            fillColor: '#2e7d32',
            fillOpacity: 0.3,
            stroke: true,
            color: '#2e7d32',
            weight: 2,
            opacity: 0.8
          }
        },
        interactive: true,
        getFeatureId: (f: { properties: { id?: string; osm_id?: string } }) =>
          f.properties.id ?? String(f.properties.osm_id ?? '')
      }
    ).addTo(this.map);

    vectorTileLayer.on('click', (e: L.LeafletMouseEvent) => {
      console.log('[map] vector tile click', e);
      const ev = e as L.LeafletMouseEvent & { layer?: { properties?: Record<string, unknown> } };
      console.log('[map] ev.layer', ev.layer, 'ev.target', (ev as unknown as { target?: unknown }).target);
      const props = ev.layer?.properties ?? (ev as unknown as { target?: { properties?: Record<string, unknown> } }).target?.properties;
      console.log('[map] props', props);
      const rawId = props?.['id'] != null ? String(props['id']) : undefined;
      const osmType = props?.['osm_type'] != null ? String(props['osm_type']) : undefined;
      console.log('[map] extracted id', rawId, 'osm_type', osmType);
      const id = rawId ? this.normalizeReserveId(rawId, osmType) : undefined;
      if (id) this.loadReserve(id);
      else console.log('[map] no id in props, not loading reserve');
    });
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
