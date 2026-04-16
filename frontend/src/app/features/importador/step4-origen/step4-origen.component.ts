import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NgClass } from '@angular/common';
import { ImportadorService } from '../../../core/services/importador.service';
import {
  OPCIONES_ORIGEN,
  OrigenCorreo,
  OrigenDatos,
  OrigenSftp,
  OrigenTeams,
  TipoOrigen,
  crearOrigenVacio,
} from '../../../core/models/origen.model';

@Component({
  selector: 'app-step4-origen',
  standalone: true,
  imports: [FormsModule, NgClass],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="paso4">
      <section class="app-card seccion">
        <header class="seccion-header">
          <div>
            <h2>Origen de datos</h2>
            <p class="subtitulo">
              Indica desde dónde se tomarán los archivos del mandante para cargas recurrentes.
            </p>
          </div>
        </header>

        <div class="grid-origen">
          @for (opcion of opciones; track opcion.tipo) {
            <button
              type="button"
              class="card-origen"
              [ngClass]="{ 'card-origen--activo': origenActual()?.tipo === opcion.tipo }"
              (click)="seleccionar(opcion.tipo)"
            >
              <span class="card-titulo">{{ opcion.titulo }}</span>
              <span class="card-desc">{{ opcion.descripcion }}</span>
              @if (origenActual()?.tipo === opcion.tipo) {
                <span class="card-check" aria-hidden="true">&#10003;</span>
              }
            </button>
          }
        </div>

        @if (origenActual(); as origen) {
          <div class="formulario">
            @if (origen.tipo === 'sftp') {
              <div class="grid-form">
                <div class="form-field col-span-2">
                  <label for="host">Host / servidor</label>
                  <input
                    id="host"
                    type="text"
                    class="form-control"
                    placeholder="sftp.mandante.com"
                    [ngModel]="asSftp(origen).host"
                    (ngModelChange)="actualizar({ host: $event })"
                  />
                </div>
                <div class="form-field">
                  <label for="puerto">Puerto</label>
                  <input
                    id="puerto"
                    type="number"
                    class="form-control"
                    min="1"
                    [ngModel]="asSftp(origen).puerto"
                    (ngModelChange)="actualizar({ puerto: +$event })"
                  />
                </div>
                <div class="form-field">
                  <label for="usuario">Usuario</label>
                  <input
                    id="usuario"
                    type="text"
                    class="form-control"
                    autocomplete="username"
                    [ngModel]="asSftp(origen).usuario"
                    (ngModelChange)="actualizar({ usuario: $event })"
                  />
                </div>
                <div class="form-field">
                  <label for="password">Contraseña</label>
                  <input
                    id="password"
                    type="password"
                    class="form-control"
                    autocomplete="new-password"
                    [ngModel]="asSftp(origen).password"
                    (ngModelChange)="actualizar({ password: $event })"
                  />
                </div>
                <div class="form-field col-span-2">
                  <label for="ruta">Ruta del directorio</label>
                  <input
                    id="ruta"
                    type="text"
                    class="form-control"
                    placeholder="/cargas/asignacion/"
                    [ngModel]="asSftp(origen).ruta"
                    (ngModelChange)="actualizar({ ruta: $event })"
                  />
                </div>
              </div>
            } @else if (origen.tipo === 'correo') {
              <div class="grid-form">
                <div class="form-field col-span-2">
                  <label for="direccion">Dirección de correo</label>
                  <input
                    id="direccion"
                    type="email"
                    class="form-control"
                    placeholder="cargas@mandante.com"
                    [ngModel]="asCorreo(origen).direccion"
                    (ngModelChange)="actualizar({ direccion: $event })"
                  />
                </div>
                <div class="form-field col-span-2">
                  <label for="carpeta">Carpeta</label>
                  <input
                    id="carpeta"
                    type="text"
                    class="form-control"
                    placeholder="Bandeja de entrada"
                    [ngModel]="asCorreo(origen).carpeta"
                    (ngModelChange)="actualizar({ carpeta: $event })"
                  />
                </div>
              </div>
            } @else {
              <div class="grid-form">
                <div class="form-field col-span-2">
                  <label for="equipo">Nombre del equipo</label>
                  <input
                    id="equipo"
                    type="text"
                    class="form-control"
                    placeholder="Equipo Cobranza BBVA"
                    [ngModel]="asTeams(origen).equipo"
                    (ngModelChange)="actualizar({ equipo: $event })"
                  />
                </div>
                <div class="form-field col-span-2">
                  <label for="canal">Canal</label>
                  <input
                    id="canal"
                    type="text"
                    class="form-control"
                    placeholder="Cargas diarias"
                    [ngModel]="asTeams(origen).canal"
                    (ngModelChange)="actualizar({ canal: $event })"
                  />
                </div>
              </div>
            }
          </div>
        } @else {
          <p class="vacio">Selecciona un tipo de origen para configurar sus datos de conexión.</p>
        }
      </section>

      <footer class="acciones">
        <button type="button" class="btn btn-ghost" (click)="volver()">Volver</button>
        <button
          type="button"
          class="btn btn-primary"
          [disabled]="!puedeAvanzar()"
          (click)="continuar()"
        >
          Continuar
        </button>
      </footer>
    </div>
  `,
  styleUrl: './step4-origen.component.scss',
})
export class Step4OrigenComponent {
  private readonly importador = inject(ImportadorService);
  private readonly router = inject(Router);

  readonly opciones = OPCIONES_ORIGEN;
  readonly origenActual = this.importador.origen;
  readonly puedeAvanzar = computed(() => this.importador.origenCompleto());

  seleccionar(tipo: TipoOrigen): void {
    if (this.origenActual()?.tipo === tipo) return;
    this.importador.definirOrigen(crearOrigenVacio(tipo));
  }

  actualizar(parcial: Partial<OrigenDatos>): void {
    this.importador.actualizarOrigen(parcial);
  }

  asSftp(origen: OrigenDatos): OrigenSftp {
    return origen as OrigenSftp;
  }

  asCorreo(origen: OrigenDatos): OrigenCorreo {
    return origen as OrigenCorreo;
  }

  asTeams(origen: OrigenDatos): OrigenTeams {
    return origen as OrigenTeams;
  }

  volver(): void {
    void this.router.navigate(['/importador/columnas']);
  }

  continuar(): void {
    if (!this.puedeAvanzar()) return;
    void this.router.navigate(['/importador/confirmar']);
  }
}
