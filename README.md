# GitWalk

AI-powered GitHub repository explorer that visualizes code structure, dependencies, and provides intelligent code search.

![GitWalk](https://img.shields.io/badge/GitWalk-AI%20Code%20Explorer-purple)

## Features

- **Repository Parsing** - Paste any GitHub URL to analyze the codebase
- **Multi-Language Support** - Python, JavaScript, TypeScript, Go, Java, Rust, C/C++, PHP
- **Dependency Graph** - Interactive D3.js visualization of file dependencies
- **AI Summaries** - Automatic file-level summaries using GPT-4/Gemini/etc.
- **Semantic Search** - Vector-based code search with embeddings
- **AI Chat** - Ask questions about the codebase with tool-calling capabilities

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React, TypeScript, Vite, TailwindCSS, D3.js |
| **Backend** | Python, FastAPI, Motor (async MongoDB) |
| **Database** | MongoDB Atlas (with Vector Search) |
| **AI** | OpenAI, Gemini, Fireworks (multi-provider) |
| **Parsing** | Tree-sitter (multi-language AST parsing) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │   Home   │  │ Explorer │  │  Graph   │  │    AI Chat       │ │
│  │   Page   │  │ FileTree │  │   D3.js  │  │  (Tool Calling)  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼───────────────────────────────────┐
│                        Backend (FastAPI)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │   GitHub     │  │    File      │  │      AI Service        │ │
│  │   Service    │  │  Processing  │  │  (Summary, Embedding)  │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Tree-sitter │  │   Vector     │  │     Query Service      │ │
│  │   Parsers    │  │   Search     │  │    (RAG + Tools)       │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      MongoDB Atlas                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ sessions │  │  repos   │  │  files   │  │  conversations   │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
│                    + Vector Search Indexes                       │
└─────────────────────────────────────────────────────────────────┘
```

## Processing Pipeline

```
GitHub URL → Fetch Metadata → Fetch File Tree → Parse Files (AST)
                                                      ↓
                                            Generate Embeddings
                                                      ↓
                                            Generate AI Summaries
                                                      ↓
                                            Build Dependency Graph
                                                      ↓
                                                  Complete!
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- AI API key (OpenAI, Gemini, or Fireworks)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env with your credentials
# - MONGODB_URL
# - GITHUB_TOKEN (optional, for higher rate limits)

# Run server
uvicorn app.main:app --reload --port 9999
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env

# Edit .env
# VITE_API_URL=http://localhost:9999

# Run dev server
npm run dev
```

### Environment Variables

#### Backend (.env)

```env
# MongoDB
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/dbname
DATABASE_NAME=github_explorer

# Server
HOST=0.0.0.0
PORT=9999
ENV=development

# CORS
FRONTEND_URL=http://localhost:5173

# GitHub (optional - for higher rate limits)
GITHUB_TOKEN=ghp_your_token_here

# AI (optional - can be set per session)
AI_API_KEY=
AI_PROVIDER=openai
AI_MODEL=gpt-4o-mini
```

#### Frontend (.env)

```env
VITE_API_URL=http://localhost:9999
```

## Deployment

### Backend (Render)

1. Create account at [render.com](https://render.com)
2. New → Web Service → Connect GitHub repo
3. Configure:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables
5. Deploy

### Frontend (Vercel)

1. Create account at [vercel.com](https://vercel.com)
2. Import GitHub repo
3. Configure:
   - Root Directory: `frontend`
   - Framework: Vite
4. Add environment variable: `VITE_API_URL=https://your-backend.onrender.com`
5. Deploy

## AI Tools (Function Calling)

The AI chat supports these tools:

| Tool | Description |
|------|-------------|
| `search_code` | Semantic search across code and summaries |
| `search_files` | Search files by their summaries |
| `get_repo_overview` | Get repository overview |
| `get_file_by_path` | Retrieve specific file content |
| `find_function` | Find function by exact name |

## Supported Languages

| Language | Parser | Extensions |
|----------|--------|------------|
| Python | Built-in AST | `.py` |
| JavaScript | Tree-sitter | `.js` |
| TypeScript | Tree-sitter | `.ts`, `.tsx` |
| Go | Tree-sitter | `.go` |
| Java | Tree-sitter | `.java` |
| Rust | Tree-sitter | `.rs` |
| C/C++ | Tree-sitter | `.c`, `.cpp`, `.h` |
| PHP | Tree-sitter | `.php` |

## License

MIT
