"""
SRM Syllabus Indexer
Downloads all department PDFs and indexes them into Qdrant
"""
import os
import httpx
import asyncio
from pathlib import Path
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import re

load_dotenv()

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "srm_syllabus"
CHUNK_SIZE = 500  # words per chunk
CHUNK_OVERLAP = 50

# Initialize embedding model (runs locally, free!)
print("Loading embedding model...")
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize Qdrant client
print("Connecting to Qdrant...")
qdrant = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
)


def extract_department_from_filename(filename: str) -> str:
    """Extract department name from PDF filename"""
    name = filename.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
    # Remove common suffixes
    for suffix in ['syllabus', 'curriculum', '2021', '2018', '2015', 'core', 'elective']:
        name = name.replace(suffix, '')
    return name.strip().title()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk) > 100:  # Skip very small chunks
            chunks.append(chunk)
    
    return chunks


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n\n"
        return text
    except Exception as e:
        print(f"  Error reading {pdf_path}: {e}")
        return ""


async def download_pdf(url: str, save_path: Path) -> bool:
    """Download a PDF file"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                save_path.write_bytes(response.content)
                return True
    except Exception as e:
        print(f"  Download error: {e}")
    return False


def create_collection():
    """Create or recreate Qdrant collection"""
    try:
        qdrant.delete_collection(COLLECTION_NAME)
        print("Deleted existing collection")
    except:
        pass
    
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=384,  # all-MiniLM-L6-v2 embedding size
            distance=models.Distance.COSINE
        ),
    )
    print(f"Created collection: {COLLECTION_NAME}")


async def index_pdfs():
    """Main indexing function"""
    # Read PDF links
    pdf_links_file = Path("pdf_links.txt")
    if not pdf_links_file.exists():
        print("Error: pdf_links.txt not found. Run scraping first.")
        return
    
    pdf_urls = pdf_links_file.read_text().strip().split('\n')
    print(f"Found {len(pdf_urls)} PDF links")
    
    # Create downloads directory
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    
    # Create collection
    create_collection()
    
    all_points = []
    point_id = 0
    
    for i, url in enumerate(pdf_urls):
        filename = url.split('/')[-1]
        pdf_path = downloads_dir / filename
        
        print(f"\n[{i+1}/{len(pdf_urls)}] Processing: {filename}")
        
        # Download if not exists
        if not pdf_path.exists():
            print("  Downloading...")
            success = await download_pdf(url, pdf_path)
            if not success:
                print("  ❌ Download failed, skipping")
                continue
        
        # Extract text
        print("  Extracting text...")
        text = extract_text_from_pdf(str(pdf_path))
        if not text:
            print("  ❌ No text extracted, skipping")
            continue
        
        # Chunk text
        chunks = chunk_text(text)
        print(f"  Created {len(chunks)} chunks")
        
        # Extract department info
        department = extract_department_from_filename(filename)
        
        # Generate embeddings and create points
        print("  Generating embeddings...")
        for j, chunk in enumerate(chunks):
            embedding = embedder.encode(chunk).tolist()
            
            point = models.PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "text": chunk,
                    "department": department,
                    "filename": filename,
                    "url": url,
                    "chunk_index": j,
                }
            )
            all_points.append(point)
            point_id += 1
        
        # Upload after each PDF to avoid timeout
        if all_points:
            print(f"  Uploading {len(all_points)} points...")
            try:
                qdrant.upsert(
                    collection_name=COLLECTION_NAME,
                    points=all_points
                )
                all_points = []
            except Exception as e:
                print(f"  ❌ Upload error: {e}")
                all_points = []  # Clear and continue
    
    # Upload remaining points
    if all_points:
        print(f"\nUploading final batch of {len(all_points)} points...")
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=all_points
        )
    
    # Get collection info
    info = qdrant.get_collection(COLLECTION_NAME)
    print(f"\n✅ Indexing complete!")
    print(f"   Total vectors: {info.points_count}")
    print(f"   Collection: {COLLECTION_NAME}")


if __name__ == "__main__":
    print("=" * 50)
    print("SRM Syllabus Indexer")
    print("=" * 50)
    
    if not QDRANT_URL or not QDRANT_API_KEY:
        print("Error: QDRANT_URL and QDRANT_API_KEY must be set in .env")
        exit(1)
    
    asyncio.run(index_pdfs())
