"""Controller for user management, including user and nutricionist creation and retrieval."""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from shared.database import get_db
from application.models.application_models import User, Nutricionist

router = APIRouter(prefix="/users", tags=["users"])

class UserBase(BaseModel):
    """Base model for user creation."""
    email: str
    birthdate: datetime
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

DbDependency = Annotated[Session, Depends(get_db)]

@router.post(
    "/create_User",
    responses={
        200: {"model": UserBase, "description": "User created successfully"},
    }
)
def create_user(user: UserBase, db: DbDependency):
    """Create a new user in the database."""

    new_user = User(
        email = user.email,
        birthdate = user.birthdate,
        weight_kg = user.weight_kg,
        height_m = user.height_m,
        sex = user.sex,
        password = user.password,
        nutricionist_id = user.nutricionist_id,
        is_active = True,
        created_at = user.created_at
    )

    if new_user is None:
        raise HTTPException(status_code=400, detail="User creation failed")

    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/get_User/{user_id}")
def get_user(user_id: int, db: DbDependency):
    """Retrieve a user by their ID."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/create_Nutricionist")
def create_nutricionist(nutricionist: NutricionistBase, db: DbDependency):
    """Create a new nutricionist in the database."""
    new_nutricionist = Nutricionist(
        email = nutricionist.email,
        password = nutricionist.password,
        phone = nutricionist.phone,
        created_at = nutricionist.created_at
    )

    if new_nutricionist is None:
        raise HTTPException(status_code=400, detail="Nutricionist creation failed")

    if db.query(Nutricionist).filter(Nutricionist.email == nutricionist.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db.add(new_nutricionist)
    db.commit()
    db.refresh(new_nutricionist)
    return new_nutricionist
