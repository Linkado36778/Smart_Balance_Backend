"""Controller for user management, including user and nutricionist creation and retrieval."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from ..models import application_models as models
from typing import Annotated, Optional
from shared.database import get_db, initialize_database
from sqlalchemy.orm import Session
from datetime import datetime

router = APIRouter(prefix="/users", tags=["users"])

class UserBase(BaseModel):
    """Base model for user creation."""
    email: str
    birthdate: str
    weight_kg: float
    height_m: float
    sex: str
    password: str
    created_at: datetime = Field(default_factory=datetime.now)
    nutricionist_id: Optional[int] = None

    @field_validator("created_at")
    @classmethod
    def parse_user_created_at(cls, value):
        """Parse the user_created_at field to ensure it's a datetime object."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                return datetime.fromisoformat(value)
        return value

class NutricionistBase(BaseModel):
    """Base model for nutricionist creation."""
    email: str
    password: str
    phone: str
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("created_at")
    @classmethod
    def parse_nutricionist_created_at(cls, value):
        """Parse the nutricionist_created_at field to ensure it's a datetime object."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                return datetime.fromisoformat(value)
        return value

initialize_database()

DbDependency = Annotated[Session, Depends(get_db)]

@router.post("/create_User")
def create_user(user: UserBase, db: DbDependency):
    """Create a new user in the database."""
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

    if db.query(models.User).filter(models.User.user_email == user.user_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/get_User/{user_id}")
def get_user(user_id: int, db: DbDependency):
    """Retrieve a user by their ID."""
    db_user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/create_Nutricionist")
def create_nutricionist(nutricionist: NutricionistBase, db: DbDependency):
    """Create a new nutricionist in the database."""
    db_nutricionist = models.Nutricionist(
        nutricionist_email=nutricionist.nutricionist_email,
        nutricionist_password=nutricionist.nutricionist_password,
        nutricionist_phone=nutricionist.nutricionist_phone,
        nutricionist_created_at=nutricionist.nutricionist_created_at
    )

    if db_nutricionist is None:
        raise HTTPException(status_code=400, detail="Nutricionist creation failed")

    if db.query(models.Nutricionist).filter(models.Nutricionist.nutricionist_email == nutricionist.nutricionist_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db.add(db_nutricionist)
    db.commit()
    db.refresh(db_nutricionist)
    return db_nutricionist
