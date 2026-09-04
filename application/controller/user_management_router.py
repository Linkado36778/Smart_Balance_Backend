"""Controller for user management, including user and nutricionist creation and retrieval."""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator, Field
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from shared.database import get_db
from application.models.application_models import Allergen, User, Nutricionist, UserAllergenAssociation
from application.models.return_model import ReturnModel
import re

router = APIRouter(prefix="/users", tags=["users"])
password_hash = PasswordHash.recommended()

class PostAllergenUser(BaseModel):
    """Base model for retrieving allergens by user."""
    user_id: int
    allergen_id: int

class PostCreateUserBodyRequest(BaseModel):
    """Base model for user creation."""
    email: str
    birthdate: datetime
    weight_kg: float
    height_m: float
    sex: str
    password: str
    is_active: bool
    nutricionist_id: Optional[int] = None

    @field_validator("birthdate")
    def parse_birthdate(cls, value):
        """Ensure birthdate is a datetime object."""
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise ValueError("birthdate must be in YYYY-MM-DD format")
        return value

class PostCreateNutricionistBodyRequest(BaseModel):
    """Base model for nutricionist creation."""
    email: str
    password: str
    phone: str
    crn: str

DbDependency = Annotated[Session, Depends(get_db)]

def nutricionist_validate_format(nuricionist_crn: str):
    crn_pattern = r"^CRN-\d{1} \d{5}$"
    if re.match(crn_pattern, nuricionist_crn):     
        return True
    return False

@router.post(
    "/create_User",
    responses={
        200: {"model": PostCreateUserBodyRequest, "description": "User created successfully"},
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
        is_active = user.is_active,
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
        data = {
            "id": new_user.id,
            "email": new_user.email,
            "birthdate": new_user.birthdate,
            "weight_kg": new_user.weight_kg,
            "height_m": new_user.height_m,
            "sex": new_user.sex,
            "created_at": new_user.created_at,
            "is_active": new_user.is_active
        },
        success = True
    )

@router.get("/login_User/{user_email}/{user_password}")
def login_user(user_email: str, user_password: str, db: DbDependency):
    """Login a user by their email and password."""
    db_user = db.query(User).filter(User.email == user_email).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not password_hash.verify(user_password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return db_user

@router.get("/login_Nutricionist/{nutricionist_email}/{nutricionist_password}")
def login_nutricionist(nutricionist_email: str, nutricionist_password: str, db: DbDependency):
    """Login a nutricionist by their email and password."""
    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.email == nutricionist_email).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")
    if not password_hash.verify(nutricionist_password, db_nutricionist.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return db_nutricionist

# Endpoint abaixo descontinuado, pois não é necessário para a funcionalidade atual do sistema.

# @router.get("/get_User_Allergens_by_food/{user_id}/{food_id}")
# def get_user_allergens_by_food(user_id: int, food_id: int, db: DbDependency):
#     """Retrieve a user's allergens by their ID and a specific food ID."""
#     db_user = db.query(User).filter(User.id == user_id).first()
#     if db_user is None:
#         raise HTTPException(status_code=404, detail="User not found")

#     # Assuming you have a relationship set up between User and Allergen
#     allergens = (
#     db.query(Allergen)
#     .join(UserAllergenAssociation, UserAllergenAssociation.allergen_id == Allergen.id)
#     .join(AllergenFoodAssociation, AllergenFoodAssociation.allergen_id == Allergen.id)
#     .filter(UserAllergenAssociation.user_id == user_id)
#     .filter(AllergenFoodAssociation.food_id == food_id)
#     .all()
# )
#     return allergens

@router.post("/create_Nutricionist")
def create_nutricionist(nutricionist: PostCreateNutricionistBodyRequest, db: DbDependency):
    """Create a new nutricionist in the database."""
    new_nutricionist = Nutricionist(
        email = nutricionist.email,
        password = password_hash.hash(nutricionist.password),
        phone = nutricionist.phone,
        crn = nutricionist.crn
    )

    if not nutricionist_validate_format(nutricionist.crn):
        raise HTTPException(status_code=400, detail="Invalid CRN format. Expected format: CRN-X XXXXX")

    if new_nutricionist is False:
        raise HTTPException(status_code=400, detail="Nutricionist creation failed")

    if db.query(Nutricionist).filter(Nutricionist.email == nutricionist.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db.add(new_nutricionist)
    db.commit()
    db.refresh(new_nutricionist)
    return new_nutricionist

@router.post("/add_allergen_to_user")
def add_allergen_to_user(allergen_User: PostAllergenUser, db: DbDependency):
    """Add an allergen to a user."""
    new_association = UserAllergenAssociation(
        user_id=allergen_User.user_id,
        allergen_id=allergen_User.allergen_id
    )

    if new_association is None:
        raise HTTPException(status_code=400, detail="Allergen association failed")

    db.add(new_association)
    db.commit()
    db.refresh(new_association)
    return new_association

@router.post("/link_user_nutricionist")
def link_user_nutricionist(user_id: int, nutricionist_id: int, db: DbDependency):
    """Link a user to a nutricionist."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.id == nutricionist_id).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")

    db_user.nutricionist_id = nutricionist_id
    db.commit()
    db.refresh(db_user)
    return ReturnModel(
        message = "User linked to nutricionist successfully",
        data = {
            "user_id": db_user.id,
            "nutricionist_id": db_user.nutricionist_id
        },
        success = True
    )


@router.get("/list_allergens_by_user/{user_id}")
def list_allergens_by_user(user_id: int, db: DbDependency):
    """List all allergens associated with a user."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    allergens = (
        db.query(Allergen)
        .join(UserAllergenAssociation, UserAllergenAssociation.allergen_id == Allergen.id)
        .filter(UserAllergenAssociation.user_id == user_id)
        .all()
    )
    return allergens