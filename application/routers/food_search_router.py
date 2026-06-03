from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..models import application_models as models
from typing import Annotated
from shared.database import engine, get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/food_search", tags=["food_search"])

class FoodBase(BaseModel):
    food_name: str
    category_name: str
    brand_id_FK: int

class BrandBase(BaseModel): 
    brand_name: str

models.Base.metadata.create_all(bind=engine)

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/search")
def search_food(food_name: str, db: db_dependency):
    db_food_search = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{food_name}%")).all()

    if not db_food_search:
        raise HTTPException(status_code=404, detail="Food not found")
    
    return db_food_search
    
@router.post("/add_food")
def add_food(food: FoodBase, db: db_dependency):
    db_food = models.Food(
        food_name = food.food_name,
        category_name = food.category_name,
        brand_id_FK = food.brand_id_FK
    )

    db_food_create = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{food.food_name}%")).first()

    if db_food_create is not None:
        raise HTTPException(status_code=400, detail="Food already exists")
    
    else:
        db.add(db_food)
        db.commit()
        db.refresh(db_food)

    return db_food

@router.get("/search_brand")
def search_brand(brand_name: str, db: db_dependency):
    db_brand_search = db.query(models.Brand).filter(models.Brand.brand_name.ilike(f"%{brand_name}%")).all()

    if not db_brand_search:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    return db_brand_search
    
@router.post("/add_brand")
def add_brand(brand: BrandBase, db: db_dependency):
    db_brand = models.Brand(
        brand_name = brand.brand_name
    )

    db_brand_create = db.query(models.Brand).filter(models.Brand.brand_name.ilike(f"%{brand.brand_name}%")).first()

    if db_brand_create is not None:
        raise HTTPException(status_code=400, detail="Brand already exists")
    
    else:
        db.add(db_brand)
        db.commit()
        db.refresh(db_brand)

    return db_brand
