import { Injectable } from '@angular/core';

import { SeoService } from '../core/seo.service';
import type { NatureReserveDetail, ReserveGeometry } from './reserve-detail';

const BASE_URL = 'https://opennaturemaps.org';
const WEBSITE_TAG_KEYS = ['website', 'contact:website', 'url'] as const;

@Injectable({ providedIn: 'root' })
export class ReserveSeoService {
  constructor(private seo: SeoService) {}

  set(reserve: NatureReserveDetail): void {
    const name = reserve.name ?? reserve.id;
    const title = `${name} - OpenNatureMap`;
    const description = this.buildDescription(reserve, name);
    const canonical = this.canonical(reserve.id);

    this.seo.setTitle(title);
    this.seo.setDescription(description);
    this.seo.setCanonical(canonical);
    this.seo.setOpenGraph({ title, description, url: canonical, type: 'place' });
    this.seo.setJsonLd(this.buildJsonLd(reserve, name, canonical));
  }

  canonical(id: string): string {
    return `${BASE_URL}/reserve/${id}`;
  }

  private buildDescription(reserve: NatureReserveDetail, name: string): string {
    const parts: string[] = [`Nature reserve: ${name}.`];
    const operatorNames = reserve.operators.map((o) => o.name).join(', ');
    if (operatorNames) parts.push(`Managed by ${operatorNames}.`);
    if (reserve.protect_class) parts.push(`Protection class: ${reserve.protect_class}.`);
    return parts.join(' ');
  }

  private buildJsonLd(
    reserve: NatureReserveDetail,
    name: string,
    url: string,
  ): Record<string, unknown> {
    const ld: Record<string, unknown> = {
      '@context': 'https://schema.org',
      '@type': ['TouristAttraction', 'Place'],
      name,
      url,
    };

    const centroid = reserve.geometry ? geometryCentroid(reserve.geometry) : null;
    if (centroid) {
      ld['geo'] = { '@type': 'GeoCoordinates', latitude: centroid[0], longitude: centroid[1] };
    }

    const sameAs = this.buildSameAs(reserve);
    if (sameAs.length > 0) {
      ld['sameAs'] = sameAs.length === 1 ? sameAs[0] : sameAs;
    }

    return ld;
  }

  private buildSameAs(reserve: NatureReserveDetail): string[] {
    const sameAs: string[] = [];

    const wikiRaw = reserve.tags?.['wikipedia'];
    if (typeof wikiRaw === 'string') {
      const colon = wikiRaw.indexOf(':');
      if (colon > 0) {
        const lang = wikiRaw.slice(0, colon);
        const article = wikiRaw
          .slice(colon + 1)
          .trim()
          .replace(/\s+/g, '_');
        if (lang && article) {
          sameAs.push(`https://${lang}.wikipedia.org/wiki/${encodeURIComponent(article)}`);
        }
      }
    }

    for (const key of WEBSITE_TAG_KEYS) {
      const val = reserve.tags?.[key];
      if (typeof val === 'string' && val.trim()) {
        sameAs.push(val.trim());
        break;
      }
    }

    return sameAs;
  }
}

function geometryCentroid(geometry: ReserveGeometry): [number, number] | null {
  const coords: [number, number][] = [];
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
  const lat = coords.reduce((s, c) => s + c[0], 0) / coords.length;
  const lng = coords.reduce((s, c) => s + c[1], 0) / coords.length;
  return [lat, lng];
}
