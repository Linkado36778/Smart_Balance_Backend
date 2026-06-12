"""Controller for user management, including user and nutricionist creation and retrieval."""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from shared.database import get_db
from application.models.application_models import User, Nutricionist
from application.models.return_models import ReturnModel, ReturnSuccessUserModel

router = APIRouter(prefix="/users", tags=["users"])
password_hash = PasswordHash.recommended()

class PostCreateUserBodyRequest(BaseModel):
    """Base model for user creation."""
    email: str
    birthdate: datetime
    weight_kg: float
    height_m: float
    sex: str
    password: str
    nutricionist_id: Optional[int] = None

class PostCreateNutricionistBodyRequest(BaseModel):
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
    responses = {
        200: {"model": ReturnModel, "description": "User created successfully"},
    }
)
def create_user(user: PostCreateUserBodyRequest, db: DbDependency):
    """Create a new user in the database."""

    new_user = User(
        email = user.email,
        birthdate = user.birthdate,
        weight_kg = user.weight_kg,
        height_m = user.height_m,
        sex = user.sex,
        password = password_hash.hash(user.password),
        nutricionist_id = user.nutricionist_id,
    )

    if new_user is None:
        raise HTTPException(status_code=400, detail="User creation failed")

    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return ReturnModel(
        message = "User created successfully",
        data = None,
        success = True
    )


@router.get(
    "/get_User/{user_id}",
    responses = {
        200: {"model": ReturnModel[ReturnSuccessUserModel], "description": "User getted successfully"},
    }
)
def get_user(user_id: int, db: DbDependency):
    """Retrieve a user by their ID."""
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    ret = ReturnSuccessUserModel(
        id = user.id,
        email = user.email,
        birthdate = user.birthdate,
        weight_kg = user.weight_kg,
        height_m = user.height_m,
        sex = user.sex,
        created_at = user.created_at
    )
    
    return ReturnModel(
        message = "User getted successfully",
        data = ret,
        success = True
    )


@router.post(
    "/create_Nutricionist",
    responses = {
        200: {"model": ReturnModel, "description": "Nutricionist created successfully"},
    }
)
def create_nutricionist(nutricionist: PostCreateNutricionistBodyRequest, db: DbDependency):
    """Create a new nutricionist in the database."""
    new_nutricionist = Nutricionist(
        email = nutricionist.email,
        password = password_hash.hash(nutricionist.password),
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

    return ReturnModel(
        message = "Nutricionist created successfully",
        data = None,
        success = True
    )
