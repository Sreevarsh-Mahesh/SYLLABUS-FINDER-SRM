"""
PDF Indexer for SRM Syllabus
Extracts text, chunks it, and stores in ChromaDB
"""
import os
import re
from typing import List
from pypdf import PdfReader
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY in .env file")

genai.configure(api_key=GEMINI_API_KEY)

# Custom embedding function for ChromaDB
class GeminiEmbeddingFunction:
    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings = []
        for text in input:
            try:
                result = genai.embed_content(
                    model="models/embedding-001",
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
            except Exception as e:
                print(f"Embedding error: {e}")
                embeddings.append([0.0] * 768)  # Fallback
        return embeddings


def extract_course_info(text: str) -> dict:
    """Extract course code and name from text"""
    code_match = re.search(r'(21[A-Z]{2,3}\d{3}[A-Z]?)', text)
    name_match = re.search(r'Course\s*\n?\s*Name\s+([A-Z][A-Z\s\-\&\(\)]+)', text)
    
    return {
        "code": code_match.group(1) if code_match else "",
        "name": name_match.group(1).strip() if name_match else ""
    }


def extract_unit_info(text: str) -> str:
    """Extract unit number and title"""
    unit_match = re.search(r'Unit\s*[-–]\s*(\d+)\s*[-–]?\s*([^\n]+)', text, re.IGNORECASE)
    if unit_match:
        return f"Unit {unit_match.group(1)}: {unit_match.group(2).strip()}"
    return ""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk) > 50:  # Skip very small chunks
            chunks.append(chunk)
    
    return chunks


def index_pdf(pdf_path: str, db_path: str = "./chroma_db"):
    """Main indexing function"""
    print(f"Loading PDF: {pdf_path}")
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    print(f"Total pages: {total_pages}")
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=db_path)
    embedding_fn = GeminiEmbeddingFunction()
    
    # Delete existing collection if exists
    try:
        client.delete_collection("syllabus")
    except:
        pass
    
    collection = client.create_collection(
        name="syllabus",
        embedding_function=embedding_fn
    )
    
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    current_subject = {"code": "", "name": ""}
    current_unit = ""
    
    print("Extracting and chunking text...")
    for page_num in range(total_pages):
        text = reader.pages[page_num].extract_text() or ""
        
        # Update current subject/unit context
        course_info = extract_course_info(text)
        if course_info["code"]:
            current_subject = course_info
        
        unit_info = extract_unit_info(text)
        if unit_info:
            current_unit = unit_info
        
        # Chunk the page
        chunks = chunk_text(text)
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"page_{page_num+1}_chunk_{i}"
            metadata = {
                "page": page_num + 1,
                "subject": current_subject["name"] or "Unknown",
                "subject_code": current_subject["code"],
                "unit": current_unit
            }
            
            all_chunks.append(chunk)
            all_metadatas.append(metadata)
            all_ids.append(chunk_id)
        
        if (page_num + 1) % 50 == 0:
            print(f"Processed {page_num + 1}/{total_pages} pages...")
    
    print(f"Total chunks: {len(all_chunks)}")
    
    # Add to ChromaDB in batches
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch_end = min(i + batch_size, len(all_chunks))
        print(f"Indexing batch {i//batch_size + 1}/{(len(all_chunks)-1)//batch_size + 1}...")
        
        try:
            collection.add(
                documents=all_chunks[i:batch_end],
                metadatas=all_metadatas[i:batch_end],
                ids=all_ids[i:batch_end]
            )
        except Exception as e:
            print(f"Error indexing batch: {e}")
    
    print(f"\n✅ Indexing complete! {collection.count()} chunks stored in ChromaDB")
    return collection.count()


def index_json_syllabus(json_path: str, db_path: str = "./chroma_db"):
    """Index from JSON syllabus (faster, for pre-extracted data)"""
    import json
    
    print(f"Loading JSON: {json_path}")
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=db_path)
    embedding_fn = GeminiEmbeddingFunction()
    
    try:
        client.delete_collection("syllabus")
    except:
        pass
    
    collection = client.create_collection(
        name="syllabus",
        embedding_function=embedding_fn
    )
    
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    print("Processing subjects...")
    for subject in data.get("subjects", []):
        subject_name = subject.get("name", "")
        subject_code = subject.get("code", "")
        
        for unit in subject.get("units", []):
            unit_num = unit.get("number", 0)
            unit_title = unit.get("title", "")
            topics = unit.get("topics", [])
            
            # Create a chunk for this unit
            chunk_text = f"""
Subject: {subject_name} ({subject_code})
Unit {unit_num}: {unit_title}

Topics covered:
{chr(10).join(['- ' + t for t in topics])}
"""
            chunk_id = f"{subject_code}_unit_{unit_num}"
            metadata = {
                "subject": subject_name,
                "subject_code": subject_code,
                "unit": f"Unit {unit_num}: {unit_title}",
                "unit_number": unit_num
            }
            
            all_chunks.append(chunk_text)
            all_metadatas.append(metadata)
            all_ids.append(chunk_id)
    
    print(f"Total chunks: {len(all_chunks)}")
    
    # Add to ChromaDB
    if all_chunks:
        collection.add(
            documents=all_chunks,
            metadatas=all_metadatas,
            ids=all_ids
        )
    
    print(f"\n✅ Indexing complete! {collection.count()} chunks stored in ChromaDB")
    return collection.count()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python indexer.py <pdf_path>     - Index a PDF file")
        print("  python indexer.py --json <path>  - Index a JSON syllabus")
        sys.exit(1)
    
    if sys.argv[1] == "--json":
        json_path = sys.argv[2] if len(sys.argv) > 2 else "../data/syllabus.json"
        index_json_syllabus(json_path)
    else:
        pdf_path = sys.argv[1]
        index_pdf(pdf_path)
