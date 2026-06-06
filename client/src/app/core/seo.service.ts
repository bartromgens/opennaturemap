import { Injectable, Inject } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { Title, Meta } from '@angular/platform-browser';

const BASE_URL = 'https://opennaturemaps.org';
const DEFAULT_TITLE = 'OpenNatureMap - Nature reserves on an interactive map';
const DEFAULT_DESCRIPTION = 'Browse nature reserves on an interactive map.';
const DEFAULT_URL = `${BASE_URL}/`;
const DEFAULT_OG_IMAGE = `${BASE_URL}/og-image.png`;

export interface OpenGraphMeta {
  title: string;
  description: string;
  url: string;
  type?: string;
  image?: string;
}

export interface JsonLdPlace {
  '@context': 'https://schema.org';
  '@type': string | string[];
  name: string;
  url?: string;
  geo?: {
    '@type': 'GeoCoordinates';
    latitude: number;
    longitude: number;
  };
  sameAs?: string[];
}

@Injectable({ providedIn: 'root' })
export class SeoService {
  constructor(
    private title: Title,
    private meta: Meta,
    @Inject(DOCUMENT) private document: Document,
  ) {}

  setTitle(t: string): void {
    this.title.setTitle(t);
    this.meta.updateTag({ property: 'og:title', content: t });
    this.meta.updateTag({ name: 'twitter:title', content: t });
  }

  setDescription(desc: string): void {
    this.meta.updateTag({ name: 'description', content: desc });
    this.meta.updateTag({ property: 'og:description', content: desc });
    this.meta.updateTag({ name: 'twitter:description', content: desc });
  }

  setCanonical(url: string): void {
    this.meta.updateTag({ property: 'og:url', content: url });
    let link = this.document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
      link = this.document.createElement('link');
      link.setAttribute('rel', 'canonical');
      this.document.head.appendChild(link);
    }
    link.setAttribute('href', url);
  }

  setOpenGraph({ title, description, url, type = 'website', image }: OpenGraphMeta): void {
    this.meta.updateTag({ property: 'og:title', content: title });
    this.meta.updateTag({ property: 'og:description', content: description });
    this.meta.updateTag({ property: 'og:url', content: url });
    this.meta.updateTag({ property: 'og:type', content: type });
    this.meta.updateTag({ property: 'og:image', content: image ?? DEFAULT_OG_IMAGE });
    this.meta.updateTag({ name: 'twitter:title', content: title });
    this.meta.updateTag({ name: 'twitter:description', content: description });
    this.meta.updateTag({ name: 'twitter:image', content: image ?? DEFAULT_OG_IMAGE });
  }

  setJsonLd(data: JsonLdPlace | Record<string, unknown>): void {
    this.clearJsonLd();
    const script = this.document.createElement('script');
    script.type = 'application/ld+json';
    script.setAttribute('data-seo', '');
    script.textContent = JSON.stringify(data);
    this.document.head.appendChild(script);
  }

  clearJsonLd(): void {
    const existing = this.document.querySelector('script[data-seo]');
    existing?.remove();
  }

  reset(): void {
    this.setTitle(DEFAULT_TITLE);
    this.setDescription(DEFAULT_DESCRIPTION);
    this.setCanonical(DEFAULT_URL);
    this.setOpenGraph({
      title: DEFAULT_TITLE,
      description: DEFAULT_DESCRIPTION,
      url: DEFAULT_URL,
      type: 'website',
      image: DEFAULT_OG_IMAGE,
    });
    this.clearJsonLd();
  }
}
