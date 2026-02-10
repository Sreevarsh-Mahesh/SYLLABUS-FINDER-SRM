# SRM Syllabus Finder Bot 🎓

An AI-powered chatbot to find syllabi for SRM CINTEL department subjects.

## Features
- 🔍 **Smart Search** - Natural language queries for syllabus lookup
- 📚 **Unit-wise Breakdown** - View specific units and topics
- 🤖 **AI-Powered** - Uses LLM for intelligent responses
- ⚡ **Fast** - Instant local search with AI enhancement
- 🧠 **Conversation Memory** - Redis-backed memory for follow-up questions

## Quick Start

1. Clone the repo
2. Open `index.html` in your browser
3. Start asking about syllabi!

## Example Queries
- "What is the syllabus for AgentOps?"
- "Show me Machine Learning Unit 2"
- "List all subjects"
- "What about unit 3?" (follow-up with memory!)

## Tech Stack
- HTML/CSS/JS (No framework overhead)
- FastAPI Backend (HuggingFace Spaces)
- Qdrant Vector DB (Semantic Search)
- OpenRouter API (Free LLM)
- Redis (Upstash - Conversation Memory)
- Beautiful dark theme UI

## Environment Variables (Backend)

Set these in your HuggingFace Space secrets:

```env
QDRANT_URL=https://xxx.cloud.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
REDIS_URL=redis://default:xxx@xxx.upstash.io:6379
```

### Getting a Free Redis Instance

1. Go to [Upstash](https://upstash.com/)
2. Create a free account
3. Create a new Redis database
4. Copy the Redis URL (under "Connect" > "redis-cli")
5. Add it as `REDIS_URL` secret in HuggingFace Spaces

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check with status |
| `/api/query` | POST | Main chat endpoint with memory |
| `/api/search` | POST | Direct semantic search |
| `/api/departments` | GET | List indexed departments |
| `/api/session/new` | POST | Create new chat session |
| `/api/session/clear` | POST | Clear session memory |
| `/api/session/{id}/history` | GET | Get conversation history |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend    │────▶│   Qdrant    │
│  (Vercel)   │     │ (HF Spaces)  │     │ (Vector DB) │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────┴───────┐
                    │              │
               ┌────▼────┐   ┌─────▼─────┐
               │  Redis  │   │ OpenRouter│
               │ (Memory)│   │   (LLM)   │
               └─────────┘   └───────────┘
```

## License
MIT
