import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import type { NatureReserveDetail } from '../reserve-detail';

@Component({
  selector: 'app-reserve-sidebar',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule],
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

  protected onClose(): void {
    this.closed.emit();
  }
}
