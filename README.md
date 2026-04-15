# RECSA — Importador de Datos

Módulo de importación y normalización de archivos del CRM RECSA.

---

## Requisitos

- Python 3.14+
- Node.js v24+
- Angular CLI 21+

---

## Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt --only-binary=:all:
python main.py
```

Corre en http://localhost:8000

---

## Frontend (Angular)

```bash
cd frontend
npm install --legacy-peer-deps
npm install typescript@5.9 --save-dev --legacy-peer-deps
ng serve
```

Abre http://localhost:4200
