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

SYSTEM_PROMPT = """You are a helpful and intelligent study buddy for SRM University students.
Your goal is to answer questions about the syllabus, curriculum, and course details accurately based *only* on the provided context.

**Guidelines:**
1.  **NO GUESSING:** If the user asks a vague question (e.g., "syllabus for CT1", "unit 1 topics") without specifying the subject, **STOP**. Do not assume a subject.
    *   *Correct response:* "Which subject are you asking about? (e.g., Civil Engineering, Python, Calculus)"
2.  **Format Beautifully:** Use Markdown tables for lists.
    *   Example: | Unit | Topic |
3.  **Be Friendly & Concise:** Use a conversational tone.
4.  **Accuracy First:** If the context doesn't contain the answer, admit it.
5.  **Cite Sources:** Mention if the info comes from a specific department file (e.g., "According to the Civil Engineering syllabus...").
6.  **Exam Prep:** CT1 = Units 1-2, CT2 = Units 3-4, Semester = All units.

**Structure:**
*   Greeting.
*   **Clarification** (if needed) OR **Answer** (with Tables/Lists).
*   Follow-up suggestion.
"""


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
        
        # Search Qdrant using query_points (newer API)
        from qdrant_client.http import models as rest
        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=limit,
            with_payload=True
        )
        
        context_parts = []
        sources = []
        
        for result in results.points:
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
    """Call OpenRouter API with fallback models"""
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set")
    
    # Extensive list of free models for maximum reliability (User Requested)
    models = [
        "google/gemini-2.0-flash-exp:free",
        "xiaomi/mimo-v2-flash:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "microsoft/phi-3-medium-128k-instruct:free",
        "huggingfaceh4/zephyr-7b-beta:free",
        "mistralai/mistral-7b-instruct:free",
        "liquid/lfm-40b:free",
        "meta-llama/llama-3-8b-instruct:free",
        "qwen/qwen-2-7b-instruct:free"
    ]
    
    
    last_error = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        for model in models:
            try:
                print(f"Trying model: {model}...")
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://sreevarsh-srm-study-buddy.hf.space",
                        "X-Title": "SRM Study Buddy"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 1500,
                        "temperature": 0.7
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                
                # If error, log it and try next model
                error_body = response.text
                print(f"Model {model} failed with {response.status_code}: {error_body}")
                last_error = f"{response.status_code} - {error_body}"
                
            except Exception as e:
                print(f"Exception with model {model}: {e}")
                last_error = str(e)
                continue

    # If all models fail
    raise Exception(f"All OpenRouter models failed. Last error: {last_error}")


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
        
        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=10,
            with_payload=True
        )
        
        formatted = []
        for r in results.points:
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
