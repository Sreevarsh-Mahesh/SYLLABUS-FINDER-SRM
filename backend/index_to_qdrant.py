"""
SRM Syllabus Indexer - Fixed for smaller batch uploads
"""
import os
import httpx
import asyncio
from pathlib import Path
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

# Read .env manually
with open('../.env', 'r') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, val = line.strip().split('=', 1)
            os.environ[key] = val

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "srm_syllabus"
CHUNK_SIZE = 500
BATCH_SIZE = 20  # Much smaller batch for reliable uploads

print("Loading embedding model...")
embedder = SentenceTransformer('all-MiniLM-L6-v2')

print("Connecting to Qdrant...")
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=120)


def extract_department_from_filename(filename: str) -> str:
    name = filename.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
    for suffix in ['syllabus', 'curriculum', '2021', '2018', '2015', '2024', '2025', 'core', 'elective', 'courses']:
        name = name.replace(suffix, '')
    return name.strip().title()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - 50):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk) > 100:
            chunks.append(chunk)
    return chunks


def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n\n"
        return text
    except Exception as e:
        print(f"  Error reading PDF: {e}")
        return ""


async def download_pdf(url: str, save_path: Path) -> bool:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                save_path.write_bytes(response.content)
                return True
    except Exception as e:
        print(f"  Download error: {e}")
    return False


def upload_batch(points: list, retries: int = 3) -> bool:
    """Upload with retries"""
    for attempt in range(retries):
        try:
            qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True
            )
            return True
        except Exception as e:
            if attempt < retries - 1:
                print(f"    Retry {attempt + 1}...")
                import time
                time.sleep(2)
            else:
                print(f"    ❌ Failed after {retries} attempts: {e}")
    return False


async def index_pdfs():
    pdf_links_file = Path("pdf_links.txt")
    if not pdf_links_file.exists():
        print("Error: pdf_links.txt not found")
        return
    
    pdf_urls = pdf_links_file.read_text().strip().split('\n')
    print(f"Found {len(pdf_urls)} PDF links")
    
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    
    # Get current count
    try:
        info = qdrant.get_collection(COLLECTION_NAME)
        start_count = info.points_count
        print(f"Starting count: {start_count} vectors")
    except:
        # Create collection if doesn't exist
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )
        start_count = 0
    
    # Get next point ID
    point_id = start_count
    total_uploaded = 0
    
    for i, url in enumerate(pdf_urls):
        filename = url.split('/')[-1]
        pdf_path = downloads_dir / filename
        
        print(f"\n[{i+1}/{len(pdf_urls)}] {filename}")
        
        # Download if needed
        if not pdf_path.exists():
            print("  Downloading...")
            success = await download_pdf(url, pdf_path)
            if not success:
                continue
        
        # Extract text
        text = extract_text_from_pdf(str(pdf_path))
        if not text:
            continue
        
        chunks = chunk_text(text)
        if not chunks:
            continue
            
        print(f"  {len(chunks)} chunks")
        department = extract_department_from_filename(filename)
        
        # Generate embeddings and upload in small batches
        batch_points = []
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
                }
            )
            batch_points.append(point)
            point_id += 1
            
            # Upload when batch is full
            if len(batch_points) >= BATCH_SIZE:
                if upload_batch(batch_points):
                    total_uploaded += len(batch_points)
                batch_points = []
        
        # Upload remaining
        if batch_points:
            if upload_batch(batch_points):
                total_uploaded += len(batch_points)
        
        print(f"  ✅ Uploaded (total: {total_uploaded})")
    
    # Final count
    info = qdrant.get_collection(COLLECTION_NAME)
    print(f"\n✅ Indexing complete!")
    print(f"   New vectors added: {total_uploaded}")
    print(f"   Total vectors: {info.points_count}")


if __name__ == "__main__":
    print("=" * 50)
    print("SRM Syllabus Indexer (Fixed)")
    print("=" * 50)
    asyncio.run(index_pdfs())
