import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import {
  faArrowUpFromBracket,
  faCity,
  faBell,
  faArrowTrendUp,
} from '@fortawesome/free-solid-svg-icons';
import { DropdownMenu } from './shared/components/dropdown.menu/dropdown.menu';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, FontAwesomeModule, DropdownMenu],
  templateUrl: './app.html',
})
export class App {
  faArrowUpFromBracket = faArrowUpFromBracket;
  faCity = faCity;
  faBell = faBell;
  faArrowTrendUp = faArrowTrendUp;

  menu = [
    {
      title: 'Cargas',
      icon: faArrowUpFromBracket,
      subtitles: [
        {
          text: 'Importar datos',
          href: '/cargas/importar',
        },
      ],
    },
    {
      title: 'Empresas',
      icon: faCity,
      subtitles: [
        {
          text: 'Gestión de empresas',
          href: '/empresas',
        },
        {
          text: 'Interfaces/Integraciones',
          href: '/empresas/interfaces',
        },
        {
          text: 'Plantilla de respuestas',
          href: '/empresas/plantillas',
        },
      ],
    },
  ];
}
