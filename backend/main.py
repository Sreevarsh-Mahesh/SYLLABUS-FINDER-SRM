"""
SRM Study Buddy - RAG-based Intelligent Assistant
FastAPI backend with Qdrant semantic search + OpenRouter LLM
"""
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="SRM Study Buddy API", version="2.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
COLLECTION_NAME = "srm_syllabus"

# Initialize embedding model
print("Loading embedding model...")
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize Qdrant client
qdrant = None
if QDRANT_URL and QDRANT_API_KEY:
    print("Connecting to Qdrant...")
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# System prompt
SYSTEM_PROMPT = """You are an intelligent, friendly SRM University study buddy assistant.

Your capabilities:
1. Answer questions about any subject from any department in SRM
2. Help students prepare for exams (CT1, CT2, Semester)
3. Generate study notes and summaries
4. Explain complex topics simply
5. Create study plans

Guidelines:
- Be conversational and encouraging
- Use bullet points for clarity
- When explaining topics, relate to real-world examples
- For exam prep: CT1 = Units 1-2, CT2 = Units 3-4, Semester = All units
- Always cite which department/subject the information is from
- If you don't have specific syllabus info, be honest about it

You have access to SRM's complete syllabus data across all departments."""


# Request/Response models
class QueryRequest(BaseModel):
    query: str
    history: Optional[List[dict]] = []

class QueryResponse(BaseModel):
    response: str
    sources: List[dict] = []
    success: bool = True


def search_qdrant(query: str, limit: int = 5) -> tuple[str, list]:
    """Semantic search in Qdrant"""
    if not qdrant:
        return "", []
    
    try:
        # Generate embedding for query
        query_embedding = embedder.encode(query).tolist()
        
        # Search Qdrant
        results = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            limit=limit,
            with_payload=True
        )
        
        context_parts = []
        sources = []
        
        for result in results:
            payload = result.payload
            text = payload.get("text", "")
            dept = payload.get("department", "Unknown")
            filename = payload.get("filename", "")
            
            context_parts.append(f"[{dept}]\n{text}")
            
            if dept not in [s.get("department") for s in sources]:
                sources.append({
                    "department": dept,
                    "file": filename,
                    "score": round(result.score, 3)
                })
        
        return "\n\n---\n\n".join(context_parts), sources
        
    except Exception as e:
        print(f"Qdrant search error: {e}")
        return "", []


async def call_openrouter(prompt: str) -> str:
    """Call OpenRouter API with Nvidia Nemotron model"""
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://sreevarsh-srm-study-buddy.hf.space",
                "X-Title": "SRM Study Buddy"
            },
            json={
                "model": "nvidia/nemotron-3-nano-30b-a3b:free",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1500,
                "temperature": 0.7
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenRouter error: {response.status_code}")
        
        data = response.json()
        return data["choices"][0]["message"]["content"]


@app.get("/")
async def root():
    """Health check"""
    vector_count = 0
    if qdrant:
        try:
            info = qdrant.get_collection(COLLECTION_NAME)
            vector_count = info.points_count
        except:
            pass
    
    return {
        "status": "healthy",
        "service": "SRM Study Buddy API v2.0",
        "qdrant_connected": qdrant is not None,
        "vectors_indexed": vector_count,
        "llm": "openrouter/nvidia-nemotron"
    }


@app.get("/api/departments")
async def get_departments():
    """Get list of indexed departments"""
    if not qdrant:
        return {"departments": [], "count": 0}
    
    try:
        # Scroll through to get unique departments
        results, _ = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            with_payload=True
        )
        
        departments = set()
        for point in results:
            dept = point.payload.get("department", "")
            if dept:
                departments.add(dept)
        
        return {"departments": sorted(list(departments)), "count": len(departments)}
    except Exception as e:
        return {"departments": [], "count": 0, "error": str(e)}


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Main RAG query endpoint with semantic search"""
    
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")
    
    # Semantic search in Qdrant
    context, sources = search_qdrant(request.query, limit=5)
    
    # Build prompt
    if context:
        prompt = f"""RELEVANT SYLLABUS CONTENT:
{context}

STUDENT QUESTION: {request.query}

Based on the syllabus content above, provide a helpful and accurate response. 
Cite the specific department/subject when referencing information."""
    else:
        prompt = f"""STUDENT QUESTION: {request.query}

Note: I couldn't find specific syllabus content for this query.
Provide a helpful response based on general academic knowledge, 
but mention that you don't have specific SRM syllabus data for this topic."""

    try:
        answer = await call_openrouter(prompt)
        return QueryResponse(response=answer, sources=sources, success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def semantic_search(request: QueryRequest):
    """Direct semantic search endpoint"""
    if not qdrant:
        return {"results": [], "count": 0, "error": "Qdrant not connected"}
    
    try:
        query_embedding = embedder.encode(request.query).tolist()
        
        results = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            limit=10,
            with_payload=True
        )
        
        formatted = []
        for r in results:
            formatted.append({
                "text": r.payload.get("text", "")[:500],
                "department": r.payload.get("department", ""),
                "file": r.payload.get("filename", ""),
                "score": round(r.score, 3)
            })
        
        return {"results": formatted, "count": len(formatted)}
    except Exception as e:
        return {"results": [], "count": 0, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
