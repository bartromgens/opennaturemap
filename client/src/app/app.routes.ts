import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    title: 'OpenNatureMap - Nature reserves on an interactive map',
    data: {
      description: 'Browse nature reserves on an interactive map.',
      canonical: 'https://opennaturemaps.org/',
    },
    loadComponent: () => import('./map/map.component').then((m) => m.MapComponent),
  },
  {
    path: 'reserve/:id',
    loadComponent: () => import('./map/map.component').then((m) => m.MapComponent),
  },
  {
    path: 'protection-classes',
    title: 'Protection Classes - OpenNatureMap',
    data: {
      description:
        'Learn about the IUCN protection levels used to classify nature reserves on OpenNatureMap.',
      canonical: 'https://opennaturemaps.org/protection-classes',
    },
    loadComponent: () =>
      import('./protection-classes/protection-classes.component').then(
        (m) => m.ProtectionClassesComponent,
      ),
  },
];
