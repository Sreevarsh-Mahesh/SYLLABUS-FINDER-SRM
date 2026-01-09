"""
SRM Study Buddy - RAG-based Intelligent Assistant
FastAPI backend with ChromaDB and Gemini
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import chromadb
from chromadb.utils import embedding_functions
import google.generativeai as genai

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

# Initialize Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')

# Initialize ChromaDB with Gemini embeddings
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Use Gemini for embeddings
class GeminiEmbeddingFunction:
    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings = []
        for text in input:
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(result['embedding'])
        return embeddings

# Get or create collection
try:
    embedding_fn = GeminiEmbeddingFunction() if GEMINI_API_KEY else None
    collection = chroma_client.get_or_create_collection(
        name="syllabus",
        embedding_function=embedding_fn
    )
except Exception as e:
    print(f"ChromaDB init error: {e}")
    collection = None

# System prompt for the study buddy
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


@app.get("/")
async def root():
    """Health check"""
    return {"status": "healthy", "service": "SRM Study Buddy API"}


@app.get("/api/subjects")
async def get_subjects():
    """Get list of indexed subjects"""
    if not collection:
        return {"subjects": [], "count": 0}
    
    # Get unique subjects from metadata
    results = collection.get(include=["metadatas"])
    subjects = set()
    for meta in results.get("metadatas", []):
        if meta and "subject" in meta:
            subjects.add(meta["subject"])
    
    return {"subjects": list(subjects), "count": len(subjects)}


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Main RAG query endpoint"""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    user_query = request.query
    
    # Step 1: Search for relevant context in ChromaDB
    context_text = ""
    sources = []
    
    if collection and collection.count() > 0:
        try:
            results = collection.query(
                query_texts=[user_query],
                n_results=5,
                include=["documents", "metadatas"]
            )
            
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                meta = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                context_text += f"\n---\n{doc}\n"
                sources.append({
                    "subject": meta.get("subject", "Unknown"),
                    "unit": meta.get("unit", ""),
                    "page": meta.get("page", "")
                })
        except Exception as e:
            print(f"ChromaDB query error: {e}")
    
    # Step 2: Build prompt with context
    prompt = f"""{SYSTEM_PROMPT}

SYLLABUS CONTEXT:
{context_text if context_text else "No specific context found. Answer based on general knowledge."}

CONVERSATION HISTORY:
{chr(10).join([f"{m['role']}: {m['content']}" for m in request.history[-5:]]) if request.history else "None"}

STUDENT QUESTION: {user_query}

Provide a helpful, accurate response:"""

    # Step 3: Generate response with Gemini
    try:
        response = model.generate_content(prompt)
        answer = response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")
    
    return QueryResponse(
        response=answer,
        sources=sources,
        success=True
    )


@app.post("/api/search")
async def semantic_search(request: QueryRequest):
    """Semantic search across syllabus"""
    if not collection or collection.count() == 0:
        return {"results": [], "count": 0}
    
    try:
        results = collection.query(
            query_texts=[request.query],
            n_results=10,
            include=["documents", "metadatas"]
        )
        
        formatted_results = []
        for i, doc in enumerate(results.get("documents", [[]])[0]):
            meta = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
            formatted_results.append({
                "content": doc[:500],
                "subject": meta.get("subject", "Unknown"),
                "unit": meta.get("unit", ""),
                "page": meta.get("page", "")
            })
        
        return {"results": formatted_results, "count": len(formatted_results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
