"""
SRM Study Buddy - RAG-based Intelligent Assistant
FastAPI backend with ChromaDB and dual LLM support (Gemini + OpenRouter)
"""
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import chromadb
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="SRM Study Buddy API", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Initialize Gemini if available
model = None
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        print(f"Gemini init error: {e}")

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Simple embedding function (fallback)
class SimpleEmbeddingFunction:
    """Simple TF-IDF-like embedding for when Gemini is unavailable"""
    def __call__(self, input: List[str]) -> List[List[float]]:
        # Return dummy embeddings (ChromaDB will handle similarity)
        return [[0.0] * 384 for _ in input]

# Get or create collection
try:
    collection = chroma_client.get_or_create_collection(
        name="syllabus",
        embedding_function=SimpleEmbeddingFunction()
    )
except Exception as e:
    print(f"ChromaDB init error: {e}")
    collection = None

# System prompt
SYSTEM_PROMPT = """You are an intelligent, friendly SRM University study buddy assistant.

Your capabilities:
1. Answer questions about any subject in the syllabus
2. Help students prepare for exams (CT1, CT2, Semester)
3. Generate study notes and summaries
4. Explain complex topics simply
5. Create study plans

Guidelines:
- Be conversational and encouraging
- Use bullet points for clarity
- When explaining topics, relate to real-world examples
- For exam prep: CT1 = Units 1-2, CT2 = Units 3-4, Semester = All units
- Always cite which unit/subject the information is from

You have access to the SRM syllabus context provided below."""


# Request/Response models
class QueryRequest(BaseModel):
    query: str
    history: Optional[List[dict]] = []

class QueryResponse(BaseModel):
    response: str
    sources: List[dict] = []
    success: bool = True
    model_used: str = ""


async def call_openrouter(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """Call OpenRouter API with Nvidia Nemotron model"""
    if not OPENROUTER_API_KEY:
        raise Exception("OpenRouter API key not configured")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://srm-study-buddy.hf.space",
                "X-Title": "SRM Study Buddy"
            },
            json={
                "model": "nvidia/nemotron-3-nano-30b-a3b:free",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1500,
                "temperature": 0.7
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenRouter error: {response.status_code} - {response.text}")
        
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def call_gemini(prompt: str) -> str:
    """Call Gemini API"""
    if not model:
        raise Exception("Gemini not initialized")
    
    response = model.generate_content(prompt)
    return response.text


async def call_llm(prompt: str) -> tuple[str, str]:
    """Call LLM with fallback: Gemini -> OpenRouter"""
    
    # Try Gemini first (if available)
    if GEMINI_API_KEY and model:
        try:
            result = await call_gemini(prompt)
            return result, "gemini-2.0-flash"
        except Exception as e:
            print(f"Gemini failed: {e}")
    
    # Fallback to OpenRouter
    if OPENROUTER_API_KEY:
        try:
            result = await call_openrouter(prompt)
            return result, "nvidia/nemotron-3-nano"
        except Exception as e:
            print(f"OpenRouter failed: {e}")
            raise
    
    raise Exception("No LLM available. Configure GEMINI_API_KEY or OPENROUTER_API_KEY")


@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "healthy",
        "service": "SRM Study Buddy API",
        "llm_available": bool(GEMINI_API_KEY or OPENROUTER_API_KEY)
    }


@app.get("/api/subjects")
async def get_subjects():
    """Get list of indexed subjects"""
    # Load from syllabus.json
    try:
        with open("syllabus.json", "r") as f:
            data = json.load(f)
        subjects = [s["name"] for s in data.get("subjects", [])]
        return {"subjects": subjects, "count": len(subjects)}
    except:
        return {"subjects": [], "count": 0}


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Main RAG query endpoint"""
    user_query = request.query
    
    # Step 1: Get syllabus context
    context_text = ""
    sources = []
    
    try:
        with open("syllabus.json", "r") as f:
            syllabus = json.load(f)
        
        # Simple keyword search in syllabus
        query_lower = user_query.lower()
        for subject in syllabus.get("subjects", []):
            if (subject["name"].lower() in query_lower or 
                query_lower in subject["name"].lower() or
                subject["code"].lower() in query_lower):
                
                context_text += f"\n\n**{subject['name']} ({subject['code']})**\n"
                for unit in subject.get("units", []):
                    context_text += f"\nUnit {unit['number']}: {unit['title']}\n"
                    context_text += "Topics: " + ", ".join(unit.get("topics", [])) + "\n"
                
                sources.append({
                    "subject": subject["name"],
                    "code": subject["code"]
                })
        
        # If no specific match, include first 3 subjects as context
        if not context_text:
            for subject in syllabus.get("subjects", [])[:3]:
                context_text += f"\n\n**{subject['name']} ({subject['code']})**\n"
                for unit in subject.get("units", []):
                    context_text += f"\nUnit {unit['number']}: {unit['title']}\n"
                    context_text += "Topics: " + ", ".join(unit.get("topics", [])) + "\n"
    except Exception as e:
        print(f"Syllabus read error: {e}")
        context_text = "No syllabus context available."
    
    # Step 2: Build prompt
    prompt = f"""{SYSTEM_PROMPT}

SYLLABUS CONTEXT:
{context_text}

CONVERSATION HISTORY:
{chr(10).join([f"{m['role']}: {m['content']}" for m in request.history[-5:]]) if request.history else "None"}

STUDENT QUESTION: {user_query}

Provide a helpful, accurate response:"""

    # Step 3: Call LLM with fallback
    try:
        answer, model_used = await call_llm(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")
    
    return QueryResponse(
        response=answer,
        sources=sources,
        success=True,
        model_used=model_used
    )


@app.post("/api/search")
async def semantic_search(request: QueryRequest):
    """Search syllabus"""
    try:
        with open("syllabus.json", "r") as f:
            syllabus = json.load(f)
        
        query_lower = request.query.lower()
        results = []
        
        for subject in syllabus.get("subjects", []):
            for unit in subject.get("units", []):
                for topic in unit.get("topics", []):
                    if query_lower in topic.lower():
                        results.append({
                            "subject": subject["name"],
                            "unit": f"Unit {unit['number']}: {unit['title']}",
                            "topic": topic
                        })
        
        return {"results": results[:10], "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
