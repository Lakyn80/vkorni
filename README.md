# Vkorni — Generátor biografií

Webová aplikace pro automatické generování literárních biografií z Wikipedie, jejich obohacení o fotografie a publikaci na [vkorni.com](https://vkorni.com).

## Stack

| Vrstva | Technologie |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS |
| Backend | FastAPI (Python 3.11) |
| AI generování | DeepSeek API |
| Cache | Redis |
| Fronta úloh | RQ (Redis Queue) |
| Vektorová DB | ChromaDB (RAG / unikátnost) |
| Relační DB | SQLite + SQLAlchemy |
| Rámečky fotek | Pillow + Google Fonts (TTF) |
| Kontejnerizace | Docker Compose |

---

## Architektura

```
vkorni/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routery
│   │   │   ├── admin.py       — admin auth (login, change-password, reset)
│   │   │   ├── biography.py   — generování, cache CRUD, wiki lookup
│   │   │   ├── batch.py       — hromadné zpracování
│   │   │   ├── export.py      — publikace na vkorni.com
│   │   │   ├── images.py      — image jobs, /api/frame endpoint
│   │   │   └── styles.py      — styly pro generování
│   │   ├── db/
│   │   │   ├── sqlalchemy_db.py   — SQLite modely (Biography, Photo, AdminUser)
│   │   │   ├── photos_repo.py     — CRUD pro fotografie
│   │   │   ├── redis_client.py    — Redis cache helpers
│   │   │   └── chroma_client.py   — ChromaDB klient
│   │   ├── services/
│   │   │   ├── wiki_service.py        — stahování dat z Wikipedie/Wikidaty
│   │   │   ├── deepseek_service.py    — generování textu přes DeepSeek API
│   │   │   ├── frame_service.py       — generování memoriálních rámečků (Pillow)
│   │   │   ├── vkorny_export.py       — publikace vlákna na vkorni.com (XenForo API)
│   │   │   ├── cache_service.py       — uložení/čtení biografií z Redis
│   │   │   ├── chroma_service.py      — RAG kontext pro styly
│   │   │   ├── uniqueness_service.py  — detekce podobnosti s Wikipedií
│   │   │   ├── batch_service.py       — správa batch jobů
│   │   │   └── image_pipeline.py      — zpracování a filtrování fotek
│   │   └── workers/
│   │       ├── bio_worker.py      — RQ worker pro generování biografií
│   │       └── image_worker.py    — RQ worker pro zpracování fotek
│   ├── frames/
│   │   └── fonts/             — Google Fonts TTF (Cinzel, Playfair, Garamond…)
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx               — hlavní stránka (generování, cache, export)
│   │   ├── admin/
│   │   │   ├── login/page.tsx     — přihlašovací stránka
│   │   │   └── page.tsx           — admin dashboard (změna hesla)
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ProfileCard.tsx        — zobrazení profilu + export
│   │   ├── MemorialFrame.tsx      — náhled memoriálního rámečku
│   │   ├── PhotoGrid.tsx          — výběr fotografie
│   │   ├── BatchPanel.tsx         — hromadné zpracování
│   │   ├── CacheList.tsx          — seznam uložených profilů
│   │   └── GenerateForm.tsx       — vstupní formulář
│   ├── hooks/
│   │   ├── useProfiles.ts         — správa profilů + frame generování
│   │   ├── useAdmin.ts            — admin auth stav
│   │   ├── useBatch.ts            — batch polling
│   │   └── useCacheList.ts        — cache seznam
│   ├── middleware.ts              — ochrana všech rout (JWT cookie)
│   └── Dockerfile
└── docker-compose.yml
```

---

## Spuštění

### Požadavky
- Docker Desktop

### 1. Konfigurace `.env`

Zkopíruj `.env.example` (nebo uprav `.env`) a vyplň:

```env
# DeepSeek AI
DEEPSEEK_KEY=sk-...

# VKorni.com (XenForo API)
VKORNI_BASE_URL=https://vkorni.com/api
VKORNI_API_KEY=...
VKORNI_NODE_ID=8
VKORNI_USER_ID=1

# Backend public URL (pro inline fotky v XenForo)
BACKEND_PUBLIC_URL=http://localhost:8020

# Frontend API base
NEXT_PUBLIC_API_BASE=http://localhost:8020

# Admin — změň před nasazením na produkci!
JWT_SECRET=change-me-before-deploy
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

### 2. Spuštění

```bash
docker compose up --build
```

| Služba | URL |
|---|---|
| Frontend | http://localhost:3014 |
| Backend API | http://localhost:8020 |
| API docs | http://localhost:8020/docs |

### 3. První přihlášení

Přejdi na **http://localhost:3014** → automatický redirect na `/admin/login`.

Přihlas se s credentials z `.env` (výchozí: `admin` / `admin123`).

Po přihlášení doporučujeme heslo změnit přes `/admin`.

---

## API přehled

### Biografie
| Metoda | Endpoint | Popis |
|---|---|---|
| `POST` | `/api/generate?name=...` | Vygeneruj biografii |
| `GET` | `/api/cache` | Seznam uložených profilů |
| `GET` | `/api/cache/{name}` | Načti uložený profil |
| `DELETE` | `/api/cache/{name}` | Smaž profil z cache |

### Export
| Metoda | Endpoint | Popis |
|---|---|---|
| `POST` | `/api/export` | Publikuj profil na vkorni.com |
| `POST` | `/api/frame` | Vygeneruj memoriální rámeček |

### Batch
| Metoda | Endpoint | Popis |
|---|---|---|
| `POST` | `/api/batch` | Spusť hromadné generování |
| `GET` | `/api/batch/{id}` | Stav batch jobu |
| `POST` | `/api/batch/{id}/retry` | Opakuj neúspěšné |

### Admin
| Metoda | Endpoint | Auth | Popis |
|---|---|---|---|
| `POST` | `/api/admin/login` | — | Přihlášení → JWT token |
| `POST` | `/api/admin/change-password` | Bearer JWT | Změna hesla |
| `POST` | `/api/admin/reset-token` | Bearer JWT | Generuj reset token |
| `POST` | `/api/admin/reset-password` | — | Reset hesla tokenem |

---

## Memoriální rámečky

Backend generuje 10 grafických stylů rámečků pro portréty (Pillow):
- Cinzel, Playfair Display, EB Garamond, Crimson Text, Cormorant…

Rámeček se generuje automaticky po načtení profilu a zobrazí se jako náhled před exportem. Při exportu se nahraje na XenForo CDN a vloží jako `[IMG]` tag.

---

## Vývoj

Soubory mimo Docker (lokálně) — backend vyžaduje Python 3.11+:

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -r requirements.txt  # nebo viz Dockerfile
uvicorn app.main:app --reload --port 8020
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```
