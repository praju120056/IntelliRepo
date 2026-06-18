# GitParse — Repository Intelligence Engine

> **Graph-RAG without LLMs** · Understand any GitHub codebase through dependency graphs, call graphs, and semantic search.

---

## Architecture

```
GitHub URL
    ↓ Phase 1: Ingestion (GitPython)
Repository Clone
    ↓ Phase 2: AST Extraction (Python ast)
Structured Metadata
    ↓ Phase 3: Graph Construction (NetworkX)
Dependency + Call Graph
    ↓ Phase 4: Embedding (sentence-transformers)
Vector Representations
    ↓ Phase 5: Vector Index (ChromaDB)
    ↓ Phase 6: Graph-Aware Retrieval
    ↓ Phase 7: Query Engine (BFS/DFS)
Answers + Visualizations
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure (optional — data stored in ~/.gitparse by default)
copy .env.example .env

# Start server
uvicorn main:app --reload --port 8000
```

Backend runs at: http://localhost:8000  
API docs at: http://localhost:8000/docs

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs at: http://localhost:5173

---

## Data Storage

All persistent data lives **outside the project root** at `~/.gitparse/` (configurable via `GITPARSE_DATA_DIR` env var):

```
~/.gitparse/
├── workspaces/   # Temp cloned repos (deleted immediately post-analysis)
├── graphs/       # Serialized NetworkX graphs (.json)
└── chroma_db/    # ChromaDB persistent vector store
```

Repos are automatically evicted after **3 hours of inactivity**.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/repos/analyze` | Start repository analysis |
| `GET`  | `/api/v1/repos/{id}` | Get analysis status |
| `GET`  | `/api/v1/repos/{id}/tree` | Get file tree |
| `GET`  | `/api/v1/repos/{id}/graph` | Get full graph |
| `GET`  | `/api/v1/repos/{id}/graph/deps` | Import dependency graph |
| `GET`  | `/api/v1/repos/{id}/graph/calls` | Function call graph |
| `POST` | `/api/v1/repos/{id}/search` | Semantic search |
| `POST` | `/api/v1/repos/{id}/query` | Graph traversal query |

### Query Types

```json
{
  "type": "callers_of",      // what functions call X?
  "target": "authenticate_user",
  "depth": 3
}
```

Available types: `callers_of`, `dependencies_of`, `importers_of`, `call_chain`, `impact_of`

---

## MVP Query Examples

```bash
# Semantic search
curl -X POST http://localhost:8000/api/v1/repos/{id}/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication logic", "top_k": 10}'

# What calls this function?
curl http://localhost:8000/api/v1/repos/{id}/query/callers/authenticate_user

# Impact analysis
curl http://localhost:8000/api/v1/repos/{id}/query/impact/auth/login.py

# Call chain
curl http://localhost:8000/api/v1/repos/{id}/query/chain/main
```

---

## Engineering Principles

- **Graph is source of truth** — all structural knowledge lives in NetworkX
- **Embeddings provide semantic understanding** — `all-MiniLM-L6-v2` model
- **Vector DB answers "what is relevant?"** — ChromaDB cosine similarity
- **Graph answers "what is connected?"** — BFS/DFS traversal
- **No LLMs in the core pipeline** — deterministic, explainable, fast
- **Ephemeral source files** — cloned repos deleted immediately after parsing

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| Git | GitPython |
| AST | Python `ast` stdlib |
| Graph | NetworkX |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector DB | ChromaDB (persistent) |
| Frontend | React 18 + TypeScript + Vite |
| Graph UI | React Flow (@xyflow/react) + Dagre |
| State | Zustand |
| HTTP | Axios |

---

## Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
```
