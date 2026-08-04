# KnowledgeBase

Independent R&D testing knowledge base. It supports document upload, parsing, chunking, search, optional Qdrant indexing, source-grounded AI chat, feedback, governance views, and basic login roles.

## Local Run

```powershell
D:\.virtualenvs\KnowledgeBase\Scripts\python.exe -m pip install -r backend\requirements.txt
D:\.virtualenvs\KnowledgeBase\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8018
```

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

- Frontend: http://127.0.0.1:5188/
- Backend docs: http://127.0.0.1:8018/docs
- Default account: admin / admin123

Default local database is `backend/knowledgebase.db`. To use MySQL, create `backend/.env` and set:

```text
DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3318/knowledge_base?charset=utf8mb4
```

## Supported Knowledge Files

- Text: `.txt`, `.md`
- Word: `.docx`
- PDF: `.pdf`
- Spreadsheet: `.xlsx`, `.csv`

Excel parsing turns sheets, headers, and rows into searchable text. Old `.xls` files are not supported in the first version; save them as `.xlsx` first.

## Docker Isolation

This project uses the Compose project name `knowledgebase`. Containers and volumes use the `knowledgebase-` prefix and do not reuse APITestPlatform containers, networks, volumes, or ports.

Default ports:

- MySQL: `3318 -> 3306`
- Qdrant HTTP: `6338 -> 6333`
- Qdrant gRPC: `6339 -> 6334`
- Backend: `8018 -> 8000`
- Frontend: `5188 -> 80`

Start only dependencies:

```powershell
Copy-Item .env.docker.example .env
docker compose up -d mysql qdrant
```

Start full app:

```powershell
docker compose --profile app up -d
```

Do not use `docker system prune`, `docker volume prune`, or stop containers from other projects.

