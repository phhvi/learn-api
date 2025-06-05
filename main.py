import os
import secrets
from typing import List, Optional

from fastapi import FastAPI, HTTPException, status, Depends, Security, Response
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base # For older SQLAlchemy, or use from sqlalchemy.orm import declarative_base for newer
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    print("Error: DATABASE_URL environment variable not set.")
    exit(1)

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- API Key Authentication --- 
# Consider moving API_KEY to your .env file for better security
API_KEY = os.getenv("API_KEY") 
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

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

# --- SQLAlchemy Database Model ---
class DBItem(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, index=True)
    price = Column(Float)
    description = Column(String, nullable=True)
    is_offer = Column(Boolean, default=False, nullable=True)

# --- Pydantic Models ---
class ItemBase(BaseModel):
    name: str
    price: float
    description: Optional[str] = None
    is_offer: Optional[bool] = None

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    is_offer: Optional[bool] = None

class ItemResponse(ItemBase):
    id: int

    class Config:
        from_attributes = True

# --- FastAPI Application ---
app = FastAPI(title="Item Management API with PostgreSQL")

# --- Database Initialization ---
@app.on_event("startup")
def on_startup():
    print("Attempting to create database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables checked/created successfully.")
    except Exception as e:
        print(f"Error creating database tables: {e}")

# --- Dependency to get DB session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- CRUD Endpoints ---

@app.post("/items/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item_endpoint(item: ItemCreate, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    print(f"[CREATE_DB] Attempting to create item with data: {item}")
    db_item = DBItem(**item.model_dump())
    try:
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        print(f"[CREATE_DB] Item {db_item.id} created: {db_item.name}")
        return db_item
    except Exception as e:
        db.rollback()
        print(f"[CREATE_DB] Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create item in database.")

@app.get("/items/{item_id}", response_model=ItemResponse)
def read_item_endpoint(item_id: int, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    print(f"[READ_DB] Attempting to read item_id: {item_id}")
    db_item = db.query(DBItem).filter(DBItem.id == item_id).first()
    if db_item is None:
        print(f"[READ_DB] Item {item_id} NOT FOUND in database")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item with id {item_id} not found")
    print(f"[READ_DB] Item {item_id} FOUND: {db_item.name}")
    return db_item

@app.get("/items/", response_model=List[ItemResponse])
def list_items_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    print(f"[LIST_DB] Attempting to list items (skip={skip}, limit={limit})")
    items = db.query(DBItem).offset(skip).limit(limit).all()
    print(f"[LIST_DB] Returning {len(items)} items.")
    return items

@app.put("/items/{item_id}", response_model=ItemResponse)
def update_item_endpoint(item_id: int, item_update: ItemUpdate, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    print(f"[UPDATE_DB] Attempting to update item_id: {item_id} with data: {item_update}")
    db_item = db.query(DBItem).filter(DBItem.id == item_id).first()
    if db_item is None:
        print(f"[UPDATE_DB] Item {item_id} NOT FOUND for update")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item with id {item_id} not found")

    update_data = item_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update provided.")

    for key, value in update_data.items():
        setattr(db_item, key, value)
    
    try:
        db.add(db_item) # or db.merge(db_item) if you want to handle detached instances
        db.commit()
        db.refresh(db_item)
        print(f"[UPDATE_DB] Item {item_id} updated to: {db_item.name}")
        return db_item
    except Exception as e:
        db.rollback()
        print(f"[UPDATE_DB] Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update item in database.")

@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item_endpoint(item_id: int, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    print(f"[DELETE_DB] Attempting to delete item_id: {item_id}")
    db_item = db.query(DBItem).filter(DBItem.id == item_id).first()
    if db_item is None:
        print(f"[DELETE_DB] Item {item_id} NOT FOUND for deletion")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item with id {item_id} not found")
    
    try:
        db.delete(db_item)
        db.commit()
        print(f"[DELETE_DB] Item {item_id} DELETED")
        # Return Response with 204 status code explicitly for DELETE operations
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        print(f"[DELETE_DB] Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete item from database.")

# --- Other Endpoints (can be kept or modified as needed) ---
@app.get("/")
def read_root():
    return {"Hello": "World", "message": "Welcome to the Item Management API with PostgreSQL"}

@app.get("/generate-api-key")
def generate_api_key_endpoint():
    """Generate a random API key for demo purposes"""
    # Note: This doesn't store or manage the key, just generates one.
    return {"generated_key": secrets.token_urlsafe(32)}