import { Component, AfterViewInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import * as L from 'leaflet';
import 'leaflet.vectorgrid';

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [CommonModule, MatToolbarModule],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css'
})
export class MapComponent implements AfterViewInit, OnDestroy {
  private map: L.Map | null = null;

  ngAfterViewInit(): void {
    this.initMap();
  }

  ngOnDestroy(): void {
    if (this.map) {
      this.map.remove();
    }
  }

  private initMap(): void {
    this.map = L.map('map', {
      center: [52.0907, 5.1214],
      zoom: 11
    });

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
