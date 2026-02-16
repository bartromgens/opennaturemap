import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import type { NatureReserveDetail } from '../reserve-detail';
import { getProtectionLevelLabel, protectionLevelFromProtectClass } from '../protection-class';

@Component({
  selector: 'app-reserve-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, MatButtonModule, MatIconModule],
  templateUrl: './reserve-sidebar.component.html',
  styleUrl: './reserve-sidebar.component.css',
})
export class ReserveSidebarComponent {
  readonly expanded = input.required<boolean>();
  readonly reserve = input<NatureReserveDetail | null>(null);
  readonly error = input<string | null>(null);

  readonly closed = output<void>();

  protected objectKeys(obj: Record<string, unknown>): string[] {
    return Object.keys(obj ?? {});
  }

  protected operatorNames(reserve: NatureReserveDetail): string {
    return (reserve.operators ?? []).map((op) => op.name).join(', ');
  }

  protected wikipediaUrl(reserve: NatureReserveDetail): string | null {
    const raw = reserve.tags?.['wikipedia'];
    if (typeof raw !== 'string') return null;
    const colon = raw.indexOf(':');
    if (colon <= 0) return null;
    const lang = raw.slice(0, colon);
    const title = raw
      .slice(colon + 1)
      .trim()
      .replace(/\s+/g, '_');
    if (!lang || !title) return null;
    return `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(title)}`;
  }

  protected websiteUrl(reserve: NatureReserveDetail): string | null {
    const keys = ['website', 'contact:website', 'url'];
    for (const key of keys) {
      const val = reserve.tags?.[key];
      if (typeof val === 'string' && val.trim().length > 0) return val.trim();
    }
    return null;
  }

  protected onClose(): void {
    this.closed.emit();
  }

  protected protectionBadgeText(reserve: NatureReserveDetail): string | null {
    const pc = reserve.protect_class;
    if (pc == null || String(pc).trim() === '') return null;
    return getProtectionLevelLabel(pc) ?? String(pc).trim();
  }

  protected protectionBadgeClass(reserve: NatureReserveDetail): string {
    const value = protectionLevelFromProtectClass(reserve.protect_class);
    return value != null ? `protection-badge protection-badge--${value}` : 'protection-badge';
  }
}
