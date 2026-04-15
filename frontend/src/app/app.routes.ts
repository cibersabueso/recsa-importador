import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'importador',
    pathMatch: 'full',
  },
  {
    path: 'importador',
    loadComponent: () =>
      import('./features/importador/importador.component').then((m) => m.ImportadorComponent),
    children: [
      {
        path: '',
        redirectTo: 'subir',
        pathMatch: 'full',
      },
      {
        path: 'subir',
        loadComponent: () =>
          import('./features/importador/step1-subir/step1-subir.component').then(
            (m) => m.Step1SubirComponent,
          ),
      },
      {
        path: 'formato',
        loadComponent: () =>
          import('./features/importador/step2-formato/step2-formato.component').then(
            (m) => m.Step2FormatoComponent,
          ),
      },
      {
        path: 'columnas',
        loadComponent: () =>
          import('./features/importador/step3-columnas/step3-columnas.component').then(
            (m) => m.Step3ColumnasComponent,
          ),
      },
      {
        path: 'confirmar',
        loadComponent: () =>
          import('./features/importador/step4-confirmar/step4-confirmar.component').then(
            (m) => m.Step4ConfirmarComponent,
          ),
      },
    ],
  },
  {
    path: '**',
    redirectTo: 'importador',
  },
];
