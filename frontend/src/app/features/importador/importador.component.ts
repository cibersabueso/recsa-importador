import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterOutlet, NavigationEnd } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map, startWith } from 'rxjs/operators';
import { StepperComponent, PasoStepper } from '../../shared/components/stepper/stepper.component';
import { ImportadorService } from '../../core/services/importador.service';

@Component({
  selector: 'app-importador',
  standalone: true,
  imports: [RouterOutlet, StepperComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="importador-layout">
      <header class="header">
        <div class="marca">
          <span class="logo">RECSA</span>
          <span class="divisor"></span>
          <span class="modulo">Importador de Datos</span>
        </div>
        <div class="accion-reset">
          <button type="button" class="btn btn-ghost" (click)="reiniciar()">
            Nueva importación
          </button>
        </div>
      </header>

      <section class="stepper-wrap">
        <app-stepper [pasos]="pasos()" [pasoActual]="pasoActual()" />
      </section>

      <section class="contenido">
        <router-outlet />
      </section>
    </div>
  `,
  styleUrl: './importador.component.scss',
})
export class ImportadorComponent {
  private readonly router = inject(Router);
  private readonly importador = inject(ImportadorService);

  private readonly rutaActual = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map((e) => e.urlAfterRedirects),
      startWith(this.router.url),
    ),
    { initialValue: this.router.url },
  );

  readonly pasoActual = computed(() => {
    const url = this.rutaActual();
    if (url.includes('/subir')) return 1;
    if (url.includes('/formato')) return 2;
    if (url.includes('/columnas')) return 3;
    if (url.includes('/confirmar')) return 4;
    return 1;
  });

  readonly pasos = computed<PasoStepper[]>(() => [
    { id: 1, titulo: 'Subir archivos', ruta: '/importador/subir', habilitado: true },
    {
      id: 2,
      titulo: 'Configurar formato',
      ruta: '/importador/formato',
      habilitado: this.importador.puedeIrAPaso2(),
    },
    {
      id: 3,
      titulo: 'Revisar columnas',
      ruta: '/importador/columnas',
      habilitado: this.importador.puedeIrAPaso3(),
    },
    {
      id: 4,
      titulo: 'Confirmar',
      ruta: '/importador/confirmar',
      habilitado: this.importador.puedeIrAPaso4(),
    },
  ]);

  reiniciar(): void {
    this.importador.resetear();
    void this.router.navigate(['/importador/subir']);
  }
}
