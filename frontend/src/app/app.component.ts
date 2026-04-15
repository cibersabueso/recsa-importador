import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="app-shell">
      <router-outlet />
    </main>
  `,
  styles: [
    `
      .app-shell {
        min-height: 100vh;
        background: var(--color-bg);
      }
    `,
  ],
})
export class AppComponent {}
