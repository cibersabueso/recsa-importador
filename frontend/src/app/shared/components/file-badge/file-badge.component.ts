import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TipoArchivo } from '../../../core/models/archivo.model';

interface EstiloBadge {
  fondo: string;
  color: string;
  borde: string;
}

const ESTILOS: Record<TipoArchivo, EstiloBadge> = {
  csv: { fondo: '#e1eef8', color: '#1e6091', borde: '#bcd9ef' },
  txt: { fondo: '#ede5dc', color: '#5c4a33', borde: '#d9cbb7' },
  xlsx: { fondo: '#e6f4ea', color: '#1e6b2e', borde: '#b8dcc3' },
  xml: { fondo: '#f3e8f9', color: '#6b2e8e', borde: '#dcc2ea' },
  json: { fondo: '#fff3dd', color: '#a05e00', borde: '#f0d9a1' },
};

@Component({
  selector: 'app-file-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span
      class="file-badge"
      [style.background]="estilo().fondo"
      [style.color]="estilo().color"
      [style.border-color]="estilo().borde"
    >
      {{ etiqueta() }}
    </span>
  `,
  styles: [
    `
      .file-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 3px 8px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        border-radius: 6px;
        border: 1px solid transparent;
        line-height: 1;
      }
    `,
  ],
})
export class FileBadgeComponent {
  readonly tipo = input.required<TipoArchivo>();

  readonly etiqueta = computed(() => this.tipo().toUpperCase());
  readonly estilo = computed(() => ESTILOS[this.tipo()]);
}
