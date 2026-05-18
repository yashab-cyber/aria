import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from config import config
import uuid
from typing import List, Dict, Any

class VectorStore:
    def __init__(self):
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(path=config.chroma_persist_dir)
        
        # Load embedding model (runs locally)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize collections
        self.conv_collection = self.client.get_or_create_collection(name="conversations")
        self.kb_collection = self.client.get_or_create_collection(name="knowledge_base")
        self.wf_collection = self.client.get_or_create_collection(name="workflows")

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Convert text to vector embeddings using sentence-transformers
        embeddings = self.embedding_model.encode(texts)
        return embeddings.tolist()

    def add_to_collection(self, collection_name: str, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str] = None):
        if not ids:
            ids = [str(uuid.uuid4()) for _ in texts]
            
        embeddings = self._get_embeddings(texts)
        
        collection = self._get_collection(collection_name)
        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        return ids

    def search_collection(self, collection_name: str, query: str, n_results: int = 5, where: dict = None) -> Dict[str, Any]:
        query_embedding = self._get_embeddings([query])[0]
        collection = self._get_collection(collection_name)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )
        return results

    def _get_collection(self, collection_name: str):
        """Route a collection name to its ChromaDB collection object."""
        mapping = {
            "conversations": self.conv_collection,
            "knowledge_base": self.kb_collection,
            "workflows": self.wf_collection,
        }
        collection = mapping.get(collection_name)
        if collection is None:
            raise ValueError(f"Unknown collection: {collection_name}")
        return collection

    def delete_from_collection(self, collection_name: str, ids: List[str] = None, where: dict = None):
        """Delete documents from a collection by IDs or filter."""
        collection = self._get_collection(collection_name)
        if ids:
            collection.delete(ids=ids)
        elif where:
            collection.delete(where=where)

    def update_metadata(self, collection_name: str, ids: List[str], metadatas: List[Dict[str, Any]]):
        """Update metadata for existing documents."""
        collection = self._get_collection(collection_name)
        collection.update(ids=ids, metadatas=metadatas)

    def get_collection_count(self, collection_name: str) -> int:
        """Return the number of documents in a collection."""
        collection = self._get_collection(collection_name)
        return collection.count()

store = VectorStore()
