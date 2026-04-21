# 🅰️ Frontend – Angular 17+ · Standalone Components

> Proyecto Full Stack · Frontend con Arquitectura Modular, Tailwind CSS y TypeScript

---

## 🗂️ Estructura de Archivos

```
src/
├── app/
│   ├── core/                           ← Servicios singleton, guards, interceptors
│   │   ├── guards/
│   │   │   └── auth.guard.ts
│   │   ├── interceptors/
│   │   │   └── auth.interceptor.ts     ← Inyecta Bearer Token automáticamente
│   │   └── services/
│   │       └── api.service.ts          ← HTTP client base
│   │
│   ├── shared/                         ← Componentes, pipes y directivas reutilizables
│   │   ├── components/
│   │   │   ├── button/
│   │   │   ├── modal/
│   │   │   └── table/
│   │   ├── pipes/
│   │   │   └── date-format.pipe.ts
│   │   └── directives/
│   │       └── click-outside.directive.ts
│   │
│   ├── features/
│   │   ├── auth/
│   │   │   ├── pages/
│   │   │   │   ├── login/
│   │   │   │   └── register/
│   │   │   ├── services/
│   │   │   │   └── auth.service.ts
│   │   │   ├── models/
│   │   │   │   └── auth.model.ts
│   │   │   └── auth.routes.ts
│   │   │
│   │   ├── user/
│   │   │   ├── components/             ← Componentes "tontos" (solo presentación)
│   │   │   │   └── user-card/
│   │   │   ├── pages/                  ← Componentes "inteligentes" (lógica)
│   │   │   │   ├── user-list/
│   │   │   │   └── user-detail/
│   │   │   ├── services/
│   │   │   │   └── user.service.ts
│   │   │   ├── models/
│   │   │   │   └── user.model.ts
│   │   │   └── user.routes.ts
│   │   │
│   │   └── product/
│   │       └── ... (misma estructura)
│   │
│   └── app.routes.ts                   ← Lazy loading por módulo
│
├── environments/
│   ├── environment.ts
│   └── environment.production.ts
├── styles.css                          ← Solo @tailwind directives
└── tailwind.config.js
```

---

## 🏛️ Arquitectura

### Modular con Lazy Loading

Cada módulo de negocio tiene sus propias rutas, servicios y modelos. Se carga bajo demanda:

```typescript
// app.routes.ts
export const routes: Routes = [
  {
    path: 'users',
    loadChildren: () => import('./modules/user/user.routes').then((m) => m.USER_ROUTES),
  },
  {
    path: 'products',
    loadChildren: () => import('./modules/product/product.routes').then((m) => m.PRODUCT_ROUTES),
  },
];
```

### Responsabilidad Única (SRP)

| Clase/Archivo           | Única responsabilidad               |
| ----------------------- | ----------------------------------- |
| `user.service.ts`       | Comunicarse con la API de usuarios  |
| `user-list` (page)      | Orquestar la lógica de listado      |
| `user-card` (component) | Renderizar la tarjeta de un usuario |
| `auth.interceptor.ts`   | Agregar el token a cada request     |
| `auth.guard.ts`         | Proteger rutas privadas             |

### Standalone Components + Signals

Sin `NgModule`. Estado reactivo simple con Signals:

```typescript
// user-list.component.ts
@Component({
  standalone: true,
  selector: 'app-user-list',
  imports: [CommonModule, UserCardComponent],
  templateUrl: './user-list.component.html',
})
export class UserListComponent {
  private userService = inject(UserService);

  users = signal<User[]>([]);
  loading = signal(false);

  ngOnInit() {
    this.loading.set(true);
    this.userService.getAll().subscribe({
      next: (data) => this.users.set(data),
      complete: () => this.loading.set(false),
    });
  }
}
```

### Factory Method en Frontend

Centraliza la creación de objetos desde la respuesta de la API:

```typescript
// models/user.model.ts
export class User {
  private constructor(
    public readonly id: string,
    public readonly name: string,
    public readonly email: string,
  ) {}

  static create(data: Record<string, unknown>): User {
    return new User(String(data['id']), String(data['name']), String(data['email']));
  }
}
```

---

## ⚙️ Stack Tecnológico

| Herramienta     | Versión | Rol                          |
| --------------- | ------- | ---------------------------- |
| Angular         | 21+     | Framework principal          |
| TypeScript      | 5.x     | Lenguaje tipado              |
| RxJS            | 7.x     | Programación reactiva / HTTP |
| Tailwind CSS    | 3.x     | Estilos utility-first        |
| Angular Signals | nativo  | Estado reactivo simple       |
| Angular Router  | nativo  | Routing + Lazy Loading       |

---

## 🧪 Calidad de Código

### ESLint — Linting

Detecta errores, malas prácticas y violaciones de estilo en TypeScript y HTML. Se configura con las reglas específicas de Angular ESLint.

```bash
# Instalar
ng add @angular-eslint/schematics

# Ejecutar
ng lint

# Auto-fix
npx eslint src --fix
```

Configuración básica en `.eslintrc.json`:

```json
{
  "extends": ["plugin:@angular-eslint/recommended"],
  "rules": {
    "@angular-eslint/component-selector": ["error", { "prefix": "app", "style": "kebab-case" }],
    "@typescript-eslint/no-explicit-any": "warn"
  }
}
```

### Prettier — Formatter

Formatea TypeScript, HTML, CSS y JSON de forma uniforme. Se combina con ESLint para separar las reglas de **calidad** (ESLint) de las reglas de **estilo** (Prettier).

```bash
npm install --save-dev prettier eslint-config-prettier

# Formatear todo
npx prettier --write "src/**/*.{ts,html,css,json}"

# Verificar sin aplicar
npx prettier --check "src/**/*.{ts,html,css}"
```

Configuración en `.prettierrc`:

```json
{
  "singleQuote": true,
  "semi": true,
  "tabWidth": 2,
  "printWidth": 100,
  "trailingComma": "es5"
}
```

### Tests Unitarios — Jest / Karma

Tests para servicios, componentes y pipes. Con Standalone Components es más sencillo aislar cada pieza.

```bash
# Ejecutar tests
ng test

# Con coverage
ng test --code-coverage

# Headless (CI)
ng test --watch=false --browsers=ChromeHeadless
```

Ejemplo de test de un servicio:

```typescript
describe('UserService', () => {
  let service: UserService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [UserService],
    });
    service = TestBed.inject(UserService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('should fetch users', () => {
    service.getAll().subscribe((users) => expect(users.length).toBe(2));
    const req = httpMock.expectOne('/api/users');
    req.flush([{ id: '1' }, { id: '2' }]);
  });
});
```

---

## ✅ Ventajas de este Stack

- **Lazy loading** – el bundle inicial es mínimo; cada módulo carga cuando se necesita.
- **Signals** – estado reactivo sin la complejidad de NgRx para casos simples.
- **Standalone Components** – no más `NgModule`, menos boilerplate.
- **Tailwind** – sin CSS propio por componente, consistencia de diseño garantizada.
- **TypeScript estricto** – errores detectados en tiempo de compilación, no en runtime.
- **Interceptors** – autenticación y manejo de errores HTTP en un solo lugar.

---

## 🎨 Configuración Tailwind

```javascript
// tailwind.config.js
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        primary: '#0D9488', // teal-600
        secondary: '#1E293B', // slate-800
        accent: '#5EEAD4', // teal-300
      },
    },
  },
  plugins: [],
};
```

```css
/* styles.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

---

## 🔧 Recomendaciones

1. **Interceptor para auth** – inyecta el Bearer Token en todas las requests desde `auth.interceptor.ts`.
2. **Smart vs Dumb components** – `pages/` tienen lógica; `components/` solo reciben `@Input()`.
3. **Centraliza URLs** – define los endpoints en `environment.ts`, nunca inline.
4. **Reactive Forms** – usa `FormBuilder` en vez de Template-driven para validaciones complejas.
5. **Manejo de errores** – captura errores HTTP en el interceptor y muestra toasts/mensajes centralizados.

---

## 🚀 Próximos Pasos

- [ ] Fase 1 – Configurar GitHub Actions para build y lint
- [ ] Fase 1 – Dockerizar con nginx para producción
- [ ] Fase 1 – Escribir tests de componentes con Jest
- [ ] Fase 2 – Completar Guards y flujo de auth (login/refresh token)
- [ ] Fase 2 – Implementar Interceptor de errores globales
- [ ] Fase 3 – Optimizar imágenes y bundle (lazy images, preload)
- [ ] Fase 3 – Deploy en Vercel / Netlify con variables de entorno

---

## 📦 Instalación

```bash
git clone <repo>
cd frontend-angular

npm install
cp src/environments/environment.example.ts src/environments/environment.ts

# Configurar apiUrl en environment.ts
ng serve
```

---

> Stack: Angular 21 · TypeScript · TailwindCSS · Signals · Standalone Components
