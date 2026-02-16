import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./map/map.component').then((m) => m.MapComponent),
  },
  {
    path: 'protection-classes',
    loadComponent: () =>
      import('./protection-classes/protection-classes.component').then(
        (m) => m.ProtectionClassesComponent,
      ),
  },
];
