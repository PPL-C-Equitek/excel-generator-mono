# excel-generator-mono

[![Backend CI](https://github.com/PPL-C-Equitek/excel-generator-mono/actions/workflows/backend.yml/badge.svg)](https://github.com/PPL-C-Equitek/excel-generator-mono/actions/workflows/backend.yml)
[![Frontend CI](https://github.com/PPL-C-Equitek/excel-generator-mono/actions/workflows/frontend.yml/badge.svg)](https://github.com/PPL-C-Equitek/excel-generator-mono/actions/workflows/frontend.yml)
![Backend Coverage](.github/badges/backend-coverage.svg)
![Frontend Coverage](.github/badges/frontend-coverage.svg)

Monorepo for `Excel Generator` project (`backend` Django + `frontend` Next.js).

## System Prerequisites
- Python 3.11+
- Node.js 20+
- npm
- PostgreSQL 16+
- Linux packages: `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-eng`, `tesseract-ocr-ind`, `libmagic1`

## Tech Stack
Tech stack details are documented in [TECH-STACK.md](./TECH-STACK.md).

## How to Run

### Linux system dependencies
Install the required native packages first:

```bash
sudo apt update
sudo apt install -y poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-ind libmagic1
```

### Environment files
Create the backend environment file in the repository root:

```bash
cp .env.example .env
```

Create the frontend environment file:

```bash
cp .env.example frontend/.env
```

### Backend
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Update the root `.env` with the required local values.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Apply migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the backend server:
   ```bash
   python manage.py runserver
   ```

### Frontend
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Update `frontend/.env` if the backend runs on a different URL.
3. Install dependencies:
   ```bash
   npm install
   ```
4. Start the frontend server:
   ```bash
   npm run dev
   ```

### Optional: initialize database with seed data
```bash
bash scripts/init-db.sh
```

## How to Run Tests and Coverage

### Backend
Run the full Django test suite with coverage:

```bash
cd backend
coverage run --rcfile=.coveragerc manage.py test
coverage report
coverage xml
```

### Frontend
Run the full frontend test suite:

```bash
cd frontend
npm run test
```

Run the frontend test suite with coverage:

```bash
cd frontend
npm run test:coverage
```

Coverage badges are updated automatically by the `backend.yml` and `frontend.yml` workflows on pushes to `main`.
