import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { NgClass } from '@angular/common';

export interface PasoStepper {
  id: number;
  titulo: string;
  ruta: string;
  habilitado: boolean;
}

@Component({
  selector: 'app-stepper',
  standalone: true,
  imports: [NgClass],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ol class="stepper">
      @for (paso of pasos(); track paso.id; let idx = $index) {
        <li
          class="paso"
          [ngClass]="{
            activo: paso.id === pasoActual(),
            completado: paso.id < pasoActual(),
            deshabilitado: !paso.habilitado && paso.id !== pasoActual()
          }"
        >
          <div class="circulo">
            @if (paso.id < pasoActual()) {
              <span class="check">&#10003;</span>
            } @else {
              <span class="num">{{ paso.id }}</span>
            }
          </div>
          <div class="meta">
            <span class="rotulo">Paso {{ paso.id }}</span>
            <span class="titulo">{{ paso.titulo }}</span>
          </div>
          @if (idx < pasos().length - 1) {
            <div class="conector" [ngClass]="{ completado: paso.id < pasoActual() }"></div>
          }
        </li>
      }
    </ol>
  `,
  styleUrl: './stepper.component.scss',
})
export class StepperComponent {
  readonly pasos = input.required<PasoStepper[]>();
  readonly pasoActual = input.required<number>();
}
