from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from ..models import application_models as models
from typing import Annotated
from shared.database import engine, get_db
from sqlalchemy.orm import Session
from datetime import datetime

router = APIRouter(prefix="/users", tags=["users"])

class UserBase(BaseModel):
    user_email: str
    user_birthdate: str
    user_weight_kg: float
    user_height_m: float
    user_sex: bool
    user_password: str
    user_created_at: datetime = Field(default_factory=datetime.now)
    nutricionist_id_FK: int

    @field_validator("user_created_at")
    def parse_user_created_at(cls, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                return datetime.fromisoformat(value)
        return value

class NutricionistBase(BaseModel):
    nutricionist_email: str
    nutricionist_password: str
    nutricionist_phone: str
    nutricionist_created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("nutricionist_created_at")
    def parse_nutricionist_created_at(cls, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                return datetime.fromisoformat(value)
        return value

models.Base.metadata.create_all(bind=engine)

db_dependency = Annotated[Session, Depends(get_db)]

@router.post("/create_User")
def create_user(user: UserBase, db: db_dependency):
    db_user = models.User(
        user_email=user.user_email,
        user_birthdate=user.user_birthdate,
        user_weight_kg=user.user_weight_kg,
        user_height_m=user.user_height_m,
        user_sex=user.user_sex,
        user_password=user.user_password,
        nutricionist_id_FK=user.nutricionist_id_FK
    )

    db_user.user_birthdate = datetime.strptime(user.user_birthdate, "%d/%m/%Y").date()

    if db_user is None:
        raise HTTPException(status_code=400, detail="User creation failed")

    elif db.query(models.User).filter(models.User.user_email == user.user_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    else:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    return db_user 
    

@router.get("/get_User/{user_id}")
def get_user(user_id: int, db: db_dependency):
    db_user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/create_Nutricionist")
def create_nutricionist(nutricionist: NutricionistBase, db: db_dependency):
    db_nutricionist = models.Nutricionist(
        nutricionist_email=nutricionist.nutricionist_email,
        nutricionist_password=nutricionist.nutricionist_password,
        nutricionist_phone=nutricionist.nutricionist_phone,
        nutricionist_created_at=nutricionist.nutricionist_created_at
    )

    if db_nutricionist is None:
        raise HTTPException(status_code=400, detail="Nutricionist creation failed")

    elif db.query(models.Nutricionist).filter(models.Nutricionist.nutricionist_email == nutricionist.nutricionist_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    else:
        db.add(db_nutricionist)
        db.commit()
        db.refresh(db_nutricionist)
    return db_nutricionist