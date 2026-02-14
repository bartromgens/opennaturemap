import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import type { NatureReserveListItem } from '../reserve-detail';

@Component({
  selector: 'app-reserve-picker',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './reserve-picker.component.html',
  styleUrl: './reserve-picker.component.css',
})
export class ReservePickerComponent {
  readonly reserves = input.required<NatureReserveListItem[]>();
  readonly loading = input<boolean>(false);

  readonly reserveSelected = output<NatureReserveListItem>();
  readonly closed = output<void>();

  protected onSelect(item: NatureReserveListItem): void {
    this.reserveSelected.emit(item);
  }

  protected onClose(): void {
    this.closed.emit();
  }
}
