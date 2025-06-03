from typing import Union, List, Dict, Optional
import secrets

from fastapi import FastAPI, HTTPException, status, Response, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

app = FastAPI(title="Item Management API")

# In-memory database
items_db: Dict[int, Dict] = {}

# API Key configuration
API_KEY = "your-super-secret-api-key"
API_KEY_NAME = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Authentication dependency
async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key header was not provided"
        )
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key_header


class Item(BaseModel):
    name: str
    price: float
    description: Optional[str] = None
    is_offer: Optional[bool] = None


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    description: Optional[str] = None
    is_offer: Optional[bool] = None


@app.get("/")
def read_root():
    return {"Hello": "World", "message": "Welcome to the Item Management API"}


@app.get("/generate-api-key")
def generate_api_key():
    """Generate a random API key for demo purposes"""
    return {"generated_key": secrets.token_urlsafe(32)}


@app.get("/items/{item_id}", response_model=ItemResponse)
def read_item(item_id: int, api_key: str = Depends(get_api_key)):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found")
    
    item = items_db[item_id]
    return {"id": item_id, **item}


@app.post("/items/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(item: Item, api_key: str = Depends(get_api_key)):
    # Generate a new ID (in a real app, this would be handled by the database)
    item_id = len(items_db) + 1
    item_dict = item.model_dump()
    items_db[item_id] = item_dict
    
    return {"id": item_id, **item_dict}


@app.get("/items/", response_model=List[ItemResponse])
def list_items(api_key: str = Depends(get_api_key)):
    return [{
        "id": item_id,
        **item_data
    } for item_id, item_data in items_db.items()]


@app.put("/items/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, item: Item, api_key: str = Depends(get_api_key)):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found")
    
    item_dict = item.model_dump()
    items_db[item_id] = item_dict
    
    return {"id": item_id, **item_dict}


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, api_key: str = Depends(get_api_key)):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found")
    
    del items_db[item_id]
    return None