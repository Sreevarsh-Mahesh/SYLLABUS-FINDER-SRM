"""
SRM Study Buddy - RAG-based Intelligent Assistant
FastAPI backend with OpenRouter (Nvidia Nemotron)
"""
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
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

# API Key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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


async def call_openrouter(prompt: str) -> str:
    """Call OpenRouter API with Nvidia Nemotron model"""
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set in environment")
    
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
            raise Exception(f"OpenRouter error {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        return data["choices"][0]["message"]["content"]


def get_syllabus_context(query: str) -> tuple[str, list]:
    """Find relevant syllabus context for the query"""
    try:
        with open("syllabus.json", "r") as f:
            syllabus = json.load(f)
    except:
        return "No syllabus data available.", []
    
    context_text = ""
    sources = []
    query_lower = query.lower()
    
    # Search for matching subjects
    for subject in syllabus.get("subjects", []):
        subject_name = subject.get("name", "").lower()
        subject_code = subject.get("code", "").lower()
        
        # Check if query mentions this subject
        if (subject_name in query_lower or 
            query_lower in subject_name or
            subject_code in query_lower or
            any(word in subject_name for word in query_lower.split())):
            
            context_text += f"\n\n**{subject['name']} ({subject['code']})**\n"
            for unit in subject.get("units", []):
                context_text += f"\nUnit {unit['number']}: {unit['title']}\n"
                context_text += "Topics: " + ", ".join(unit.get("topics", [])) + "\n"
            
            sources.append({"subject": subject["name"], "code": subject["code"]})
    
    # If no specific match, provide general context
    if not context_text:
        subjects_list = [s["name"] for s in syllabus.get("subjects", [])[:5]]
        context_text = f"Available subjects: {', '.join(subjects_list)}"
    
    return context_text, sources


@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "healthy",
        "service": "SRM Study Buddy API",
        "llm": "openrouter/nvidia-nemotron",
        "api_key_set": bool(OPENROUTER_API_KEY)
    }


@app.get("/api/subjects")
async def get_subjects():
    """Get list of subjects"""
    try:
        with open("syllabus.json", "r") as f:
            data = json.load(f)
        subjects = [{"name": s["name"], "code": s["code"]} for s in data.get("subjects", [])]
        return {"subjects": subjects, "count": len(subjects)}
    except:
        return {"subjects": [], "count": 0}


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Main chat endpoint"""
    
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="OpenRouter API key not configured. Add OPENROUTER_API_KEY to Space secrets."
        )
    
    # Get syllabus context
    context, sources = get_syllabus_context(request.query)
    
    # Build prompt
    prompt = f"""SYLLABUS CONTEXT:
{context}

STUDENT QUESTION: {request.query}

Provide a helpful, accurate response based on the syllabus context above:"""

    try:
        answer = await call_openrouter(prompt)
        return QueryResponse(response=answer, sources=sources, success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search(request: QueryRequest):
    """Search syllabus topics"""
    try:
        with open("syllabus.json", "r") as f:
            syllabus = json.load(f)
        
        results = []
        query_lower = request.query.lower()
        
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
        return {"results": [], "count": 0, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
