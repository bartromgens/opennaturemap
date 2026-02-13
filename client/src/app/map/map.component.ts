import { Component, AfterViewInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import * as L from 'leaflet';
import 'leaflet.vectorgrid';

const DEFAULT_CENTER: L.LatLngTuple = [52.0907, 5.1214];
const DEFAULT_ZOOM = 11;

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [CommonModule, MatToolbarModule],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css'
})
export class MapComponent implements AfterViewInit, OnDestroy {
  private map: L.Map | null = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router
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

    const vectorTileLayer = (L as any).vectorGrid.protobuf('http://localhost:8080/data/nature_reserves/{z}/{x}/{y}.pbf', {
      vectorTileLayerStyles: {
        nature_reserves: {
          fill: true,
          fillColor: '#3388ff',
          fillOpacity: 0.3,
          stroke: true,
          color: '#3388ff',
          weight: 2,
          opacity: 0.8
        }
      },
      interactive: true,
      getFeatureId: (f: any) => f.properties.id || f.properties.osm_id
    }).addTo(this.map);
  }
}
