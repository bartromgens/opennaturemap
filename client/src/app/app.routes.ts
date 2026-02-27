import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    title: 'OpenNatureMap - Nature reserves on an interactive map',
    loadComponent: () => import('./map/map.component').then((m) => m.MapComponent),
  },
  {
    path: 'protection-classes',
    title: 'Protection Classes - OpenNatureMap',
    loadComponent: () =>
      import('./protection-classes/protection-classes.component').then(
        (m) => m.ProtectionClassesComponent,
      ),
  },
];
