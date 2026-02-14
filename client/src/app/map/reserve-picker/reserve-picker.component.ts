import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import type { NatureReserveListItem } from '../reserve-detail';

export interface PickerPosition {
  x: number;
  y: number;
}

@Component({
  selector: 'app-reserve-picker',
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule],
  templateUrl: './reserve-picker.component.html',
  styleUrl: './reserve-picker.component.css',
})
export class ReservePickerComponent {
  readonly reserves = input.required<NatureReserveListItem[]>();
  readonly loading = input<boolean>(false);
  readonly position = input<PickerPosition | null>(null);

  readonly reserveSelected = output<NatureReserveListItem>();
  readonly closed = output<void>();

  protected onSelect(item: NatureReserveListItem): void {
    this.reserveSelected.emit(item);
  }

  protected onClose(): void {
    this.closed.emit();
  }
}
