import type { Routes } from '@angular/router';
import { Dashboard } from './features/dashboard/presentation/pages/dashboard';
import { ImportarDatosIndex } from './features/importar-datos/presentation/pages/index/index';
import { ImportarDatos } from './features/importar-datos/presentation/pages/importar.datos/importar.datos';
import { ConfigurarFormato } from './features/importar-datos/presentation/pages/configurar.formato/configurar.formato';

export const routes: Routes = [
  {
    path: '',
    component: Dashboard,
  },
  {
    path: 'cargas/importar',
    component: ImportarDatosIndex,
    children: [
      {
        path: '',
        component: ImportarDatos,
      },
      {
        path: 'formato',
        component: ConfigurarFormato,
      },
    ],
  },
];
