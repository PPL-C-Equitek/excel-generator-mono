# excel-generator-mono

[![Backend CI](https://github.com/PPL-C-Equitek/excel-generator-mono/actions/workflows/backend.yml/badge.svg)](https://github.com/PPL-C-Equitek/excel-generator-mono/actions/workflows/backend.yml)
[![Frontend CI](https://github.com/PPL-C-Equitek/excel-generator-mono/actions/workflows/frontend.yml/badge.svg)](https://github.com/PPL-C-Equitek/excel-generator-mono/actions/workflows/frontend.yml)
![Backend Coverage](.github/badges/backend-coverage.svg)
![Frontend Coverage](.github/badges/frontend-coverage.svg)

Monorepo for `Excel Generator` project (`backend` Django + `frontend` Next.js).

## Checklist Tugas

- [x] Menyiapkan script run testing (minimal run-unit test & code coverage)
- [x] Menyiapkan library untuk menghitung unit test code-coverage
- [x] Menampilkan badge hasil unit test & code-coverage pada berkas `README.md` dalam repository
- [x] Menyiapkan script provisioning server, deployment, siap install dan run on staging server
- [x] Sediakan data seeding

## Test dan Coverage

Backend (Django):

```bash
cd backend
coverage run --rcfile=.coveragerc manage.py test api
coverage report
coverage xml
```

Frontend (Next.js):

```bash
cd frontend
npm run test
npm run test:coverage
```

Init DB + seed data dummy anggota:

```bash
bash scripts/init-db.sh
```

Catatan:
- Badge coverage diperbarui otomatis oleh workflow `backend.yml` dan `frontend.yml` saat ada `push` ke branch `main`.

## Tech Stack
For the tech stack details, you can read it here: [Tech Stack](./TECH-STACK.md)

## How to Run the Project
### 1. Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
2. Copy the environment file:
    ```bash
    cp .env.example .env
3. Configure the `.env` file and adjust the values as needed.
4. Install the required Python dependencies:
    ```bash
    pip install -r requirements.txt
5. Start the development server:
    ```bash
    python manage.py runserver
    ```

### 2. Frontend Setup
1. Navigate to the frontend directory:
    ```bash
    cd frontend
2. Install the required dependencies:
    ```bash
    npm install
3. Start the development server:
    ```bash
    npm run dev
    ```