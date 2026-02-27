import * as L from 'leaflet';

(window as unknown as { L: typeof L }).L = L;

import('leaflet.vectorgrid')
  .then(() => {
    return Promise.all([
      import('@angular/platform-browser'),
      import('./app/app.config'),
      import('./app/app'),
    ]);
  })
  .then(([{ bootstrapApplication }, { appConfig }, { App }]) => {
    bootstrapApplication(App, appConfig).catch((err) => console.error(err));
  });
