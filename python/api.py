from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from google import genai
from google.genai.types import EmbedContentConfig
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://cluster0.pmdqc8v.mongodb.net/?appName=Cluster0")
MONGO_USERNAME = os.getenv("MONGO_USERNAME", "mongoAtlasAdmin")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "")
GOOGLE_API_KEY_FILE = os.getenv("GOOGLE_AI_STUDIO_API_KEY_FILE", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")
EMBEDDING_MODEL = "gemini-embedding-2"
VECTOR_INDEX = "description_embedding"

mongo_client = None
collection = None
genai_client = None


def _load_api_key() -> str:
    if GOOGLE_API_KEY_FILE:
        try:
            with open(GOOGLE_API_KEY_FILE) as f:
                return f.read().strip()
        except OSError:
            pass
    return GOOGLE_API_KEY


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, collection, genai_client

    mongo_client = MongoClient(
        MONGO_URI,
        username=MONGO_USERNAME or None,
        password=MONGO_PASSWORD or None,
        authSource="admin",
    )
    collection = mongo_client["web_scraper_db"]["cve_collection"]

    api_key = _load_api_key()
    if not api_key:
        raise RuntimeError("Google AI API key not found. Set GOOGLE_AI_STUDIO_API_KEY_FILE or GOOGLE_AI_STUDIO_API_KEY.")
    genai_client = genai.Client(api_key=api_key)

    yield

    if mongo_client:
        mongo_client.close()


app = FastAPI(lifespan=lifespan)

_origins = os.getenv("ALLOWED_ORIGINS", "*")
_allow_origins = [o.strip() for o in _origins.split(",")] if _origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@app.post("/query")
def search_cves(request: QueryRequest):
    if not request.query.strip():
        print("Received empty query — returning empty results")
        return {"results": []}

    embed_response = genai_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=request.query,
        config=EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    query_vector = embed_response.embeddings[0].values

    filter_doc = {}
    if request.status:
        filter_doc["status"] = request.status
    if request.date_from or request.date_to:
        date_filter = {}
        if request.date_from:
            date_filter["$gte"] = request.date_from
        if request.date_to:
            date_filter["$lte"] = request.date_to
        filter_doc["published"] = date_filter

    vector_search = {
        "index": VECTOR_INDEX,
        "path": "description_embedding",
        "queryVector": query_vector,
        "numCandidates": 100,
        "limit": 10,
    }
    if filter_doc:
        vector_search["filter"] = filter_doc

    pipeline = [
        {"$vectorSearch": vector_search},
        {
            "$project": {
                "cve_id": 1,
                "description": 1,
                "published": 1,
                "status": 1,
                "score": {"$meta": "vectorSearchScore"},
                "_id": 0,
            }
        },
    ]

    results = list(collection.aggregate(pipeline))
    return {"results": results}
