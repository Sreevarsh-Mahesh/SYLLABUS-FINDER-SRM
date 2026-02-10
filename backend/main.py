"""
SRM Study Buddy - RAG-based Intelligent Assistant
FastAPI backend with Qdrant semantic search + OpenRouter LLM + Redis Memory
"""
import os
import json
import uuid
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
app = FastAPI(title="SRM Study Buddy API", version="2.1.0")

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
REDIS_URL = os.getenv("REDIS_URL")  # e.g., redis://default:xxx@xxx.upstash.io:6379
COLLECTION_NAME = "srm_syllabus"

# Initialize embedding model
print("Loading embedding model...")
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize Qdrant client
qdrant = None
if QDRANT_URL and QDRANT_API_KEY:
    print("Connecting to Qdrant...")
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Initialize Redis client
redis_client = None
if REDIS_URL:
    try:
        import redis
        print("Connecting to Redis...")
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        # Test connection
        redis_client.ping()
        print("✅ Redis connected successfully!")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        redis_client = None
else:
    print("⚠️ REDIS_URL not set - memory disabled")


# ============= REDIS MEMORY FUNCTIONS =============

MAX_HISTORY_MESSAGES = 20  # Keep last 20 messages per session
SESSION_EXPIRY_SECONDS = 7 * 24 * 60 * 60  # 7 days

def get_session_key(session_id: str) -> str:
    """Generate Redis key for a session"""
    return f"chat:session:{session_id}"

def save_message_to_memory(session_id: str, role: str, content: str) -> bool:
    """Save a message to Redis conversation memory"""
    if not redis_client or not session_id:
        return False
    
    try:
        key = get_session_key(session_id)
        message = json.dumps({"role": role, "content": content})
        
        # Add message to list
        redis_client.rpush(key, message)
        
        # Trim to keep only last N messages
        redis_client.ltrim(key, -MAX_HISTORY_MESSAGES, -1)
        
        # Set/reset expiry
        redis_client.expire(key, SESSION_EXPIRY_SECONDS)
        
        return True
    except Exception as e:
        print(f"Redis save error: {e}")
        return False

def get_conversation_history(session_id: str) -> List[dict]:
    """Retrieve conversation history from Redis"""
    if not redis_client or not session_id:
        return []
    
    try:
        key = get_session_key(session_id)
        messages = redis_client.lrange(key, 0, -1)
        return [json.loads(m) for m in messages]
    except Exception as e:
        print(f"Redis get error: {e}")
        return []

def clear_session_memory(session_id: str) -> bool:
    """Clear conversation history for a session"""
    if not redis_client or not session_id:
        return False
    
    try:
        key = get_session_key(session_id)
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Redis clear error: {e}")
        return False

def format_history_for_prompt(history: List[dict], max_messages: int = 6) -> str:
    """Format conversation history for LLM context"""
    if not history:
        return ""
    
    # Take only recent messages
    recent = history[-max_messages:]
    
    formatted = "\n\nPREVIOUS CONVERSATION:\n"
    for msg in recent:
        role = "Student" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "")[:500]  # Limit content length
        formatted += f"{role}: {content}\n"
    
    return formatted + "\n"


SYSTEM_PROMPT = """You are SRM Study Buddy — an intelligent syllabus assistant for SRM University students.

**YOUR CORE JOB:** Help students find subject syllabi quickly and accurately.

**CRITICAL DEFINITIONS — UNDERSTAND THE DIFFERENCE:**
- **SUBJECT** = A course with a name + code (e.g., "Machine Learning [21CSC305P]", "Data Structures and Algorithms [21CSC201J]"). This is what students want.
- **DEGREE/PROGRAM** = "B.Tech Computer Science and Engineering", "M.Tech AI and ML". This is NOT a subject. Never present degree names as subjects.
- **DEPARTMENT** = "CINTEL", "NWC", "Computing". This is an organizational unit, not a subject.

**RULES — FOLLOW EXACTLY:**

1. **WHEN A STUDENT ASKS FOR A SUBJECT (e.g., "ML", "machine learning", "NLP", "data structures"):**
   - Look through the retrieved context for ALL subjects that match or are related.
   - List them in this EXACT format (one per line):
   
     **Matching subjects:**
     1. Machine Learning [21CSC305P]
     2. Applications of Machine Learning [21CSE3XX]
     3. Quantum Machine Learning [21CSEXXX]
   
     Which one would you like the syllabus for? (Reply with the number or name)
   
   - If ONLY ONE subject matches clearly, show its complete syllabus immediately — no confirmation needed.
   - NEVER list degree programs or department names as if they were subjects.

2. **WHEN SHOWING A SYLLABUS:**
   - Show ALL units (typically Unit 1 to Unit 5).
   - List EVERY topic exactly as it appears — no shortening, no summarizing, no omitting.
   - Format:
   
     ## Subject Name [Subject Code]
     
     **Unit 1: [Title]**
     - Topic 1
     - Topic 2
     - ...
     
     **Unit 2: [Title]**
     - Topic 1
     - ...

3. **WHEN THE STUDENT SAYS "yes", a number, or confirms:**
   - Look at the PREVIOUS CONVERSATION to understand what they're confirming.
   - Show the syllabus for the confirmed subject immediately. Do NOT search for something new.
   - NEVER respond to "yes" by asking another question or showing unrelated subjects.

4. **EXAM MAPPING:**
   - CT1 = Units 1 and 2
   - CT2 = Units 3 and 4  
   - Semester Exam = All Units (1-5)
   - Still show COMPLETE unit content, not summaries.

5. **IGNORE NOISE IN CONTEXT:**
   - The retrieved context may contain degree program descriptions, prospectus text, handbook content, or department overviews.
   - IGNORE all of that. Only extract and present actual SUBJECT information (name, code, units, topics).
   - If the context contains no actual subject syllabus data, say: "I couldn't find a specific subject syllabus for that. Could you tell me the exact subject name or code?"

6. **CONVERSATION MEMORY:**
   - Use previous conversation to understand follow-ups like "what about unit 3?", "show me CT2 topics", "yes", "the first one".
   - Never lose track of which subject was being discussed.

**WHAT NOT TO DO:**
- Do NOT ask "Are you asking about B.Tech Computer Science and Engineering?" — that's a degree, not a subject.
- Do NOT enter a confirmation loop. If the student clearly named a subject, show it.
- Do NOT present prospectus/handbook/department content as syllabus answers.
- Do NOT ask more than ONE clarification question before showing results.
"""


# Request/Response models
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None  # For Redis memory
    department: Optional[str] = None  # For future department filtering
    history: Optional[List[dict]] = []  # Fallback if no Redis

class QueryResponse(BaseModel):
    response: str
    sources: List[dict] = []
    session_id: str = ""  # Return session ID to frontend
    success: bool = True

class SessionRequest(BaseModel):
    session_id: str


# ============= QUERY PREPROCESSING =============

# Common abbreviations and aliases students use → expanded search terms
SUBJECT_ALIASES = {
    "ml": "machine learning", "dl": "deep learning",
    "nlp": "natural language processing", "cv": "computer vision",
    "ai": "artificial intelligence", "ds": "data structures",
    "dsa": "data structures and algorithms", "dbms": "database management systems",
    "os": "operating systems", "cn": "computer networks",
    "coa": "computer organization and architecture",
    "daa": "design and analysis of algorithms", "iot": "internet of things",
    "cc": "cloud computing", "cns": "cryptography and network security",
    "se": "software engineering", "oops": "object oriented programming",
    "oop": "object oriented programming", "nn": "neural networks",
    "rl": "reinforcement learning", "gans": "generative adversarial networks",
    "llm": "large language models", "llms": "large language models",
    "bd": "big data", "bda": "big data analytics", "dm": "data mining",
    "ir": "information retrieval", "is": "information security",
    "cyber": "cyber security", "rpa": "robotic process automation",
    "mad": "mobile application development", "cd": "compiler design",
    "toc": "theory of computation", "flat": "formal languages and automata theory",
    "cg": "computer graphics", "maths": "mathematics",
    "la": "linear algebra", "stats": "statistics", "prob": "probability",
    "evs": "environmental science",
}

CONFIRMATION_WORDS = {
    "yes", "yeah", "yep", "yup", "ya", "sure", "correct", "right",
    "that one", "thats it", "that's it", "confirm", "ok", "okay",
    "the first one", "the second one", "the third one", "first",
    "second", "third", "1", "2", "3", "4", "5",
}


def is_confirmation(query: str) -> bool:
    q = query.strip().lower().rstrip(".!?")
    if q in CONFIRMATION_WORDS:
        return True
    if q.startswith("yes") and len(q) < 30:
        return True
    return False


def expand_query(query: str) -> str:
    q = query.strip().lower()
    if q in SUBJECT_ALIASES:
        expanded = SUBJECT_ALIASES[q]
        return f"{expanded} {query} syllabus subject course"
    words = q.split()
    expanded_words = []
    for word in words:
        clean_word = word.strip(".,!?()[]")
        if clean_word in SUBJECT_ALIASES:
            expanded_words.append(SUBJECT_ALIASES[clean_word])
        else:
            expanded_words.append(word)
    expanded = " ".join(expanded_words)
    if "syllabus" not in q and "unit" not in q and "topic" not in q:
        expanded += " syllabus subject course"
    return expanded


def extract_subject_from_history(history: List[dict]) -> str:
    if not history:
        return ""
    import re
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            code_match = re.search(r'[\[\(](21[A-Z]{2,3}\d{3}[A-Z]?)[\]\)]', content)
            if code_match:
                return code_match.group(1)
            bold_match = re.findall(r'\*\*([^*]+)\*\*', content)
            if bold_match:
                for match in bold_match:
                    if len(match) < 60 and not any(skip in match.lower() for skip in
                        ["b.tech", "btech", "m.tech", "mtech", "department", "program", "degree"]):
                        return match
    return ""


def search_qdrant(query: str, department: str = None, limit: int = 5) -> tuple[str, list]:
    """Semantic search in Qdrant with optional department filtering"""
    if not qdrant:
        return "", []
    
    try:
        # Generate embedding for query
        query_embedding = embedder.encode(query).tolist()
        
        # Build filter for department (for future use)
        from qdrant_client.http import models as rest
        query_filter = None
        if department:
            query_filter = rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="department",
                        match=rest.MatchValue(value=department)
                    )
                ]
            )
        
        # Search Qdrant
        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            query_filter=query_filter,
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


async def call_openrouter(prompt: str, conversation_context: str = "") -> str:
    """Call OpenRouter API with fallback models and conversation context"""
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set")
    
    # Build full prompt with conversation history
    full_prompt = prompt
    if conversation_context:
        full_prompt = conversation_context + "\n" + prompt
    
    # Extensive list of free models for maximum reliability
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
                            {"role": "user", "content": full_prompt}
                        ],
                        "max_tokens": 2500,
                        "temperature": 0.3
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
    """Health check with memory status"""
    vector_count = 0
    if qdrant:
        try:
            info = qdrant.get_collection(COLLECTION_NAME)
            vector_count = info.points_count
        except:
            pass
    
    return {
        "status": "healthy",
        "service": "SRM Study Buddy API v2.1",
        "qdrant_connected": qdrant is not None,
        "redis_connected": redis_client is not None,
        "memory_enabled": redis_client is not None,
        "vectors_indexed": vector_count,
        "llm": "openrouter/gemini-2.0-flash"
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
    """Main RAG query endpoint with semantic search, query expansion, and memory"""
    
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")
    
    # Generate or use session ID
    session_id = request.session_id or str(uuid.uuid4())
    
    # Get conversation history from Redis (or use fallback)
    conversation_history = []
    if redis_client and request.session_id:
        conversation_history = get_conversation_history(session_id)
    elif request.history:
        conversation_history = request.history
    
    # Format history for prompt context
    history_context = format_history_for_prompt(conversation_history)
    
    # ============= SMART QUERY HANDLING =============
    user_query = request.query.strip()
    search_query = user_query
    is_followup = is_confirmation(user_query)
    
    if is_followup:
        subject_from_history = extract_subject_from_history(conversation_history)
        if subject_from_history:
            search_query = f"{subject_from_history} syllabus complete units topics"
        else:
            search_query = user_query
    else:
        search_query = expand_query(user_query)
    
    search_limit = 8 if not is_followup else 5
    context, sources = search_qdrant(search_query, department=request.department, limit=search_limit)
    
    # ============= BUILD PROMPT =============
    if is_followup and conversation_history:
        if context:
            prompt = f"""RELEVANT SYLLABUS CONTENT:
{context}

The student's previous conversation is shown above. They just said: "{user_query}"
This is a CONFIRMATION or SELECTION — they are responding to your previous message.
Use the conversation history to understand what they want, then show the complete syllabus immediately.
Do NOT ask another clarifying question. Show the syllabus NOW."""
        else:
            prompt = f"""The student said: "{user_query}"
This is a CONFIRMATION or SELECTION responding to your previous message.
Use the conversation history to understand what subject they confirmed, and show the complete syllabus.
Do NOT ask another clarifying question."""
    elif context:
        prompt = f"""RELEVANT SYLLABUS CONTENT:
{context}

STUDENT QUESTION: {user_query}

Instructions:
- Extract ONLY actual subject information (subject name, subject code, units, topics) from the content above.
- IGNORE any degree program descriptions, prospectus text, handbook content, or department overviews.
- A subject has a code like 21CSC305P, 21CSE356T, etc. — if content doesn't have this, it's probably not a subject syllabus.
- If multiple subjects match, list them as: Subject Name [Subject Code] — let the student pick.
- If only one subject clearly matches, show the complete syllabus immediately."""
    else:
        prompt = f"""STUDENT QUESTION: {user_query}

I couldn't find specific syllabus content matching this query in the database.
Ask the student to provide the exact subject name or subject code (e.g., "Machine Learning" or "21CSC305P").
Suggest some common subjects they might be looking for based on their query."""

    try:
        # Call LLM with conversation context
        answer = await call_openrouter(prompt, history_context)
        
        # Save to Redis memory
        if redis_client:
            save_message_to_memory(session_id, "user", request.query)
            save_message_to_memory(session_id, "assistant", answer)
        
        return QueryResponse(
            response=answer, 
            sources=sources, 
            session_id=session_id,
            success=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/new")
async def create_session():
    """Create a new chat session"""
    session_id = str(uuid.uuid4())
    return {"session_id": session_id, "created": True}


@app.post("/api/session/clear")
async def clear_session(request: SessionRequest):
    """Clear conversation history for a session"""
    if not redis_client:
        return {"success": False, "error": "Memory not enabled"}
    
    success = clear_session_memory(request.session_id)
    return {"success": success, "session_id": request.session_id}


@app.get("/api/session/{session_id}/history")
async def get_session_history(session_id: str):
    """Get conversation history for a session"""
    if not redis_client:
        return {"history": [], "count": 0, "error": "Memory not enabled"}
    
    history = get_conversation_history(session_id)
    return {"history": history, "count": len(history)}


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
