---
title: SRM Study Buddy API
emoji: 📚
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# SRM Study Buddy API

RAG-based intelligent syllabus assistant for SRM University students.

## Endpoints

- `GET /` - Health check
- `GET /api/subjects` - List indexed subjects
- `POST /api/query` - Chat with study buddy
- `POST /api/search` - Semantic search

## Environment Variables

Set `GEMINI_API_KEY` in the Space secrets.
