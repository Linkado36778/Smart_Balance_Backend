"""Controller for user management, including user and nutricionist creation and retrieval."""

import os
import re
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, List, Optional
from urllib.parse import urlencode

import qrcode

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from shared.database import get_db
from application.models.application_models import Allergen, Balance, Diet, DietFoodAssociation, Food, User, Nutricionist, UserAllergenAssociation, Pairing, UserBalanceAssociation
from application.models.return_models import ReturnModel, ReturnSuccessUserModel
from application.controller.food_controller import get_visible_food

BASE_URL = os.environ.get("BASE_URL") or "http://localhost:8000"
QR_CODES_DIR = Path(__file__).resolve().parents[2] / "qr_codes"

#region Setup

router = APIRouter(tags=["User"])
DbDependency = Annotated[Session, Depends(get_db)]
password_hash = PasswordHash.recommended()
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

#region Schemas

class PostCreateBalanceBodyRequest(BaseModel):
    """Base model for balance creation."""
    id: int
    name: str

class PostCreatePairingBodyRequest(BaseModel):
    """Base model for pairing creation."""
    id: int
    token_hash: str
    scale_id: int
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)

class PostCreateDietBodyRequest(BaseModel):
    """Base model for diet creation."""
    name: str
    user_id: int
    nutricionist_id: int
    list_foods_ids: List[int] = Field(default_factory=list)
    kcal_goal: Optional[float] = None
    fat_goal: Optional[float] = None
    carb_goal: Optional[float] = None
    protein_goal: Optional[float] = None

class PostAllergenUser(BaseModel):
    """Base model for retrieving allergens by user."""
    user_id: int
    allergen_id: int

class PostCreateAllergenBodyRequest(BaseModel):
    """Base model for allergen creation."""
    name: str

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

#region Helpers

def nutricionist_validate_format(nuricionist_crn: str):
    crn_pattern = r"^CRN-\d{1} \d{5}$"
    if re.match(crn_pattern, nuricionist_crn):     
        return True
    return False

def serialize_user(user: User) -> dict:
    """Public representation of a user (never exposes the password hash)."""
    return {
        "id": user.id,
        "email": user.email,
        "birthdate": user.birthdate,
        "weight_kg": user.weight_kg,
        "height_m": user.height_m,
        "sex": user.sex,
        "created_at": user.created_at,
        "is_active": user.is_active,
        "nutricionist_id": user.nutricionist_id,
    }

def serialize_nutricionist(nutricionist: Nutricionist) -> dict:
    """Public representation of a nutricionist (never exposes the password hash)."""
    return {
        "id": nutricionist.id,
        "email": nutricionist.email,
        "phone": nutricionist.phone,
        "crn": nutricionist.crn,
        "created_at": nutricionist.created_at,
    }

#region User

@router.post(
    "/user",
    responses = {
        200: {"model": ReturnModel, "description": "User created successfully"},
    }
)
def create_user(body: PostCreateUserBodyRequest, db: DbDependency):
    """Create a new user in the database."""

    if not re.fullmatch(EMAIL_REGEX, body.email):
        raise HTTPException(status_code=400, detail="Email not valid")

    new_user = User(
        email = body.email,
        birthdate = body.birthdate,
        weight_kg = body.weight_kg,
        height_m = body.height_m,
        sex = body.sex,
        password = password_hash.hash(body.password),
        is_active = body.is_active,
        nutricionist_id = body.nutricionist_id,
    )

    if new_user is None:
        raise HTTPException(status_code=400, detail="User creation failed")

    if db.query(User).filter(User.email == body.email).first():
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

@router.patch("/update_User/{user_id}")
def update_user(user_id: int, user: PostCreateUserBodyRequest, db: DbDependency):
    """Update an existing user's information."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not re.fullmatch(EMAIL_REGEX, user.email):
        raise HTTPException(status_code=400, detail="Email not valid")

    if db.query(User).filter(User.email == user.email, User.id != user_id).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user.email = user.email
    db_user.birthdate = user.birthdate
    db_user.weight_kg = user.weight_kg
    db_user.height_m = user.height_m
    db_user.sex = user.sex
    db_user.password = password_hash.hash(user.password)
    db_user.is_active = user.is_active
    db_user.nutricionist_id = user.nutricionist_id

    db.commit()
    db.refresh(db_user)
    return ReturnModel(
        message="User updated successfully",
        data={
            "id": db_user.id,
            "email": db_user.email,
            "birthdate": db_user.birthdate,
            "weight_kg": db_user.weight_kg,
            "height_m": db_user.height_m,
            "sex": db_user.sex,
            "created_at": db_user.created_at,
            "is_active": db_user.is_active
        },
        success=True
    )

@router.delete("/delete_User/{user_id}")
def delete_user(user_id: int, db: DbDependency):
    """Delete a user from the database."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(db_user)
    db.commit()
    return ReturnModel(
        message="User deleted successfully",
        data={"id": user_id},
        success=True
    )

@router.get(
    "/user/{user_id}",
    responses = {
        200: {"model": ReturnModel[ReturnSuccessUserModel], "description": "User getted successfully"},
    }
)
def get_user(user_id: int, db: DbDependency):
    """Retrieve a user by their ID."""
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return ReturnModel(
        message = "User getted successfully",
        data = ReturnSuccessUserModel(
            id = user.id,
            email = user.email,
            birthdate = user.birthdate,
            weight_kg = user.weight_kg,
            height_m = user.height_m,
            sex = user.sex,
            created_at = user.created_at
        ),
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
    return serialize_user(db_user)

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

#region Nutricionist

@router.post(
    "/nutricionist",
    responses = {
        200: {"model": ReturnModel, "description": "Nutricionist created successfully"},
    }
)
def create_nutricionist(body: PostCreateNutricionistBodyRequest, db: DbDependency):
    """Create a new nutricionist in the database."""

    if not re.fullmatch(EMAIL_REGEX, body.email):
        raise HTTPException(status_code=400, detail="Email not valid")

    new_nutricionist = Nutricionist(
        email = body.email,
        password = password_hash.hash(body.password),
        phone = body.phone,
        crn = body.crn
    )

    if not nutricionist_validate_format(body.crn):
        raise HTTPException(status_code=400, detail="Invalid CRN format. Expected format: CRN-X XXXXX")

    if new_nutricionist is False:
        raise HTTPException(status_code=400, detail="Nutricionist creation failed")

    if db.query(Nutricionist).filter(Nutricionist.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db.add(new_nutricionist)
    db.commit()
    db.refresh(new_nutricionist)

    return ReturnModel(
        message = "Nutricionist created successfully",
        data = None,
        success = True
    )

@router.get("/get_Nutricionist/{nutricionist_id}")
def get_nutricionist(nutricionist_id: int, db: DbDependency):
    """Retrieve a nutricionist by their ID."""
    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.id == nutricionist_id).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")
    return serialize_nutricionist(db_nutricionist)

@router.patch("/update_Nutricionist/{nutricionist_id}")
def update_nutricionist(nutricionist_id: int, nutricionist: PostCreateNutricionistBodyRequest, db: DbDependency):
    """Update an existing nutricionist's information."""
    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.id == nutricionist_id).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")

    if not re.fullmatch(EMAIL_REGEX, nutricionist.email):
        raise HTTPException(status_code=400, detail="Email not valid")

    if not nutricionist_validate_format(nutricionist.crn):
        raise HTTPException(status_code=400, detail="Invalid CRN format. Expected format: CRN-X XXXXX")

    if db.query(Nutricionist).filter(Nutricionist.email == nutricionist.email, Nutricionist.id != nutricionist_id).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db_nutricionist.email = nutricionist.email
    db_nutricionist.password = password_hash.hash(nutricionist.password)
    db_nutricionist.phone = nutricionist.phone
    db_nutricionist.crn = nutricionist.crn

    db.commit()
    db.refresh(db_nutricionist)
    return ReturnModel(
        message="Nutricionist updated successfully",
        data={
            "id": db_nutricionist.id,
            "email": db_nutricionist.email,
            "phone": db_nutricionist.phone,
            "crn": db_nutricionist.crn
        },
        success=True
    )

@router.delete("/delete_Nutricionist/{nutricionist_id}")
def delete_nutricionist(nutricionist_id: int, db: DbDependency):
    """Delete a nutricionist from the database."""
    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.id == nutricionist_id).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")

    db.delete(db_nutricionist)
    db.commit()
    return ReturnModel(
        message="Nutricionist deleted successfully",
        data={"id": nutricionist_id},
        success=True
    )


@router.get("/login_Nutricionist/{nutricionist_email}/{nutricionist_password}")
def login_nutricionist(nutricionist_email: str, nutricionist_password: str, db: DbDependency):
    """Login a nutricionist by their email and password."""
    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.email == nutricionist_email).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")
    if not password_hash.verify(nutricionist_password, db_nutricionist.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return serialize_nutricionist(db_nutricionist)

@router.post("/link_user_nutricionist")
def link_user_nutricionist(user_id: int, nutricionist_CRN: str, db: DbDependency):
    """Link a user to a nutricionist."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.crn == nutricionist_CRN).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")

    db_user.nutricionist_id = db_nutricionist.id
    db.commit()
    db.refresh(db_user)
    return ReturnModel(
        message = "User linked to nutricionist successfully",
        data = {
            "user_id": db_user.id,
            "nutricionist_id": db_user.nutricionist_id,
            "nutricionist_CRN": db_nutricionist.crn
        },
        success = True
    )

@router.patch("/unlink_user_nutricionist/{user_id}")
def unlink_user_nutricionist(user_id: int, nutricionist_CRN: str, db: DbDependency):
    """Unlink a user from their nutricionist."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.crn == nutricionist_CRN).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")

    db_user.nutricionist_id = db_nutricionist.id
    
    db.commit()
    db.refresh(db_user)
    return ReturnModel(
        message = "User unlinked from nutricionist successfully",
        data = {
            "user_id": db_user.id,
            "nutricionist_id": db_user.nutricionist_id,
            "nutricionist_CRN": db_nutricionist.crn
        },
        success = True
    )

@router.get("/list_user_data_by_nutricionist/{nutricionist_id}")
def list_user_data_by_nutricionist(nutricionist_id: int, db: DbDependency):
    """List all user data associated with a nutricionist."""
    users = (
        db.query(User)
        .filter(User.nutricionist_id == nutricionist_id)
        .all()
    )
    return [serialize_user(user) for user in users]

# region Allergen

@router.post("/add_allergen_to_user")
def add_allergen_to_user(allergen_User: PostAllergenUser, db: DbDependency):
    """Add an allergen to a user."""
    if db.query(User).filter(User.id == allergen_User.user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")

    if db.query(Allergen).filter(Allergen.id == allergen_User.allergen_id).first() is None:
        raise HTTPException(status_code=404, detail="Allergen not found")

    existing_association = (
        db.query(UserAllergenAssociation)
        .filter(UserAllergenAssociation.user_id == allergen_User.user_id)
        .filter(UserAllergenAssociation.allergen_id == allergen_User.allergen_id)
        .first()
    )
    if existing_association is not None:
        raise HTTPException(status_code=400, detail="Allergen already associated with user")

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

@router.delete("/remove_allergen_from_user")
def remove_allergen_from_user(user_id: int, allergen_id: int, db: DbDependency):
    """Remove an allergen from a user."""
    association = (
        db.query(UserAllergenAssociation)
        .filter(UserAllergenAssociation.user_id == user_id)
        .filter(UserAllergenAssociation.allergen_id == allergen_id)
        .first()
    )

    if association is None:
        raise HTTPException(status_code=404, detail="Allergen association not found")

    db.delete(association)
    db.commit()
    return ReturnModel(
        message="Allergen removed from user successfully",
        data={
            "user_id": user_id,
            "allergen_id": allergen_id
        },
        success=True
    )

@router.post("/add_allergen")
def add_allergen(allergen: PostCreateAllergenBodyRequest, db: DbDependency):
    """Add a new allergen to the database."""
    new_allergen = Allergen(
        name=allergen.name
    )

    if new_allergen is None:
        raise HTTPException(status_code=400, detail="Allergen creation failed")

    db.add(new_allergen)
    db.commit()
    db.refresh(new_allergen)
    return ReturnModel(
        message="Allergen added successfully",
        data={
            "id": new_allergen.id,
            "name": new_allergen.name
        },
        success=True
    )

@router.get("/list_allergens")
def list_allergens(db: DbDependency):
    """List all allergens in the database."""
    allergens = db.query(Allergen).all()

    return [
        {
            "allergens_id": allergen.id,
            "allergens_name": allergen.name
        }
        for allergen in allergens
    ]


# region Diet

@router.post("/create_diet/{nutricionist_id}/{user_id}")
def create_diet(user_id: int, nutricionist_id: int, db: DbDependency, diet: PostCreateDietBodyRequest):
    """Create a diet for a user, linked to a nutricionist."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.id == nutricionist_id).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")

    if diet.user_id != user_id or diet.nutricionist_id != nutricionist_id:
        raise HTTPException(status_code=400, detail="Body user_id/nutricionist_id must match the route parameters")

    new_diet = Diet(
        name = diet.name,
        user_id = diet.user_id,
        nutricionist_id = diet.nutricionist_id,
        kcal_goal = diet.kcal_goal,
        fat_goal = diet.fat_goal,
        carb_goal = diet.carb_goal,
        protein_goal = diet.protein_goal
    )

    db.add(new_diet)
    db.flush()

    foods: List[Food] = []
    
    for food_id in diet.list_foods_ids:
        food = get_visible_food(db, food_id, diet.user_id)

        if food is None:
            raise HTTPException(status_code=400, detail=f"Food_id: {food_id} dont exist")
                
        foods.append(food)

    for new_food in foods:
        association = DietFoodAssociation(
            diet_id=new_diet.id,
            food_id=new_food.id
        )
        db.add(association)

    db.commit()
    db.refresh(new_diet)
    return ReturnModel(
        message = "Diet created successfully",
        data = {
            "diet_id": new_diet.id,
            "diet_name": new_diet.name,
            "user_id": new_diet.user_id,
            "nutricionist_id": new_diet.nutricionist_id
        },
        success = True
    )

@router.get("/list_diets_by_user/{user_id}")
def list_diets_by_user(user_id: int, db: DbDependency):
    """List all diets associated with a user."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    diets = (
        db.query(Diet)
        .filter(Diet.user_id == user_id)
        .all()
    )
    return diets

@router.patch("/update_diet/{diet_id}")
def update_diet(diet_id: int, diet: PostCreateDietBodyRequest, db: DbDependency):
    """Update an existing diet's information."""
    db_diet = db.query(Diet).filter(Diet.id == diet_id).first()
    if db_diet is None:
        raise HTTPException(status_code=404, detail="Diet not found")

    db_diet.name = diet.name
    db_diet.kcal_goal = diet.kcal_goal
    db_diet.fat_goal = diet.fat_goal
    db_diet.carb_goal = diet.carb_goal
    db_diet.protein_goal = diet.protein_goal

    # Remove existing food associations
    db.query(DietFoodAssociation).filter(DietFoodAssociation.diet_id == diet_id).delete()

    # Add new food associations
    for food_id in diet.list_foods_ids:
        food = get_visible_food(db, food_id, db_diet.user_id)
        if food is None:
            raise HTTPException(status_code=400, detail=f"Food_id: {food_id} does not exist")
        association = DietFoodAssociation(
            diet_id=db_diet.id,
            food_id=food.id
        )
        db.add(association)

    db.commit()
    db.refresh(db_diet)
    return ReturnModel(
        message="Diet updated successfully",
        data={
            "diet_id": db_diet.id,
            "diet_name": db_diet.name,
            "user_id": db_diet.user_id,
            "nutricionist_id": db_diet.nutricionist_id
        },
        success=True
    )

# region Balance and Pairing

@router.post("/register_balance")
def register_balance(balance: PostCreateBalanceBodyRequest, db: DbDependency):
    """Register a new balance in the database."""
    new_balance = Balance(
        name = balance.name
    )

    if new_balance is None:
        raise HTTPException(status_code=400, detail="Balance registration failed")

    db.add(new_balance)
    db.commit()
    db.refresh(new_balance)
    return ReturnModel(
        message = "Balance registered successfully",
        data = {
            "id": new_balance.id,
            "name": new_balance.name
        },
        success = True
    )



# @router.post("/register_pairing")
# def register_pairing(pairing: PostCreatePairingBodyRequest, db: DbDependency, user_id: int, balance_id: int):
#     """Register a new pairing in the database."""

#     pairing_token = secrets.token_urlsafe(32)
#     token_hash = hashlib.sha256(pairing_token.encode()).hexdigest()

#     db_user = db.query(User).filter(User.id == user_id).first()
#     if db_user is None:
#         raise HTTPException(status_code=404, detail="User not found")

#     db_balance = db.query(Balance).filter(Balance.id == balance_id).first()
#     if db_balance is None:
#         raise HTTPException(status_code=404, detail="Balance not found")

#     new_pairing = Pairing(
#         token_hash = token_hash,
#         scale_id = db_balance.id,
#         expires_at = pairing.expires_at,
#         used_at = pairing.used_at
#     )

#     if new_pairing is None:
#         raise HTTPException(status_code=400, detail="Pairing registration failed")

#     db.add(new_pairing)
#     db.commit()
#     db.refresh(new_pairing)
#     return ReturnModel(
#         message = "Pairing registered successfully",
#         data = {
#             "id": new_pairing.id,
#             "token_hash": new_pairing.token_hash,
#             "scale_id": new_pairing.scale_id,
#             "expires_at": new_pairing.expires_at,
#             "used_at": new_pairing.used_at,
#             "created_at": new_pairing.created_at
#         },
#         success = True
#     )


def hash_pairing_secret(secret: str) -> str:
    """SHA-256 of a pairing secret (QR token or poll token); only hashes are stored."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


@router.post("/generate_qr_code/")
def generate_qr_code(db: DbDependency, balance_id: Optional[int] = None):
    """Cria um token temporário e devolve seu QR Code.

    balance_id (opcional, enviado pela balança): vincula o token àquela
    balança, de modo que /pair-scale só possa parear esta balança. A resposta
    traz também poll_token, credencial que apenas quem gerou o código recebe
    (não vai no QR Code) e que autoriza GET /pairing/{pairing_id}/status.
    """

    if balance_id is not None and db.query(Balance).filter(Balance.id == balance_id).first() is None:
        raise HTTPException(status_code=404, detail="Balance not found")

    pairing_token = secrets.token_urlsafe(32)
    poll_token = secrets.token_urlsafe(32)
    validity = timedelta(minutes=5)

    db_pairing = Pairing(
        token_hash=hash_pairing_secret(pairing_token),
        expires_at=datetime.now() + validity,
        used_at=None,
        balance_id=balance_id,
        poll_token_hash=hash_pairing_secret(poll_token),
    )

    db.add(db_pairing)
    db.commit()
    db.refresh(db_pairing)

    query = {"token": pairing_token}
    if balance_id is not None:
        query["balance_id"] = balance_id
    pairing_url = f"{BASE_URL}/pair-scale?{urlencode(query)}"

    qr_image = qrcode.make(pairing_url)
    QR_CODES_DIR.mkdir(exist_ok=True)
    qr_file_name = f"pairing_{db_pairing.id}.png"
    qr_image.save(QR_CODES_DIR / qr_file_name, format="PNG")
    qr_code_url = f"{BASE_URL}/qr_codes/{qr_file_name}"

    return ReturnModel(
        message="QR code generated successfully",
        data={
            "pairing_url": pairing_url,
            "pairing_id": db_pairing.id,
            "expires_at": db_pairing.expires_at,
            # validade relativa: expires_at e hora local naive do servidor,
            # entao clientes em outro fuso usam expires_in (segundos)
            "expires_in": int(validity.total_seconds()),
            "qr_code_url": qr_code_url,
            "balance_id": db_pairing.balance_id,
            "poll_token": poll_token,
        },
        success=True,
    )

@router.post("/pair-scale")
def pair_scale(user_id: int, token: str, db: DbDependency, balance_id: Optional[int] = None):
    """Endpoint to pair a scale using a token from the QR code.

    Quando o QR Code foi gerado pela balança (token vinculado a balance_id),
    a balança é a do token: balance_id pode ser omitido e, se enviado, deve
    coincidir. Tokens antigos (sem balança) continuam exigindo balance_id.
    Parear de novo o mesmo usuário com a mesma balança é idempotente: o
    vínculo não é duplicado e o token é consumido, para a balança confirmar.
    """

    db_pairing = (
        db.query(Pairing)
        .filter(Pairing.token_hash == hash_pairing_secret(token))
        .with_for_update()
        .first()
    )

    if db_pairing is None:
        raise HTTPException(status_code=404, detail="Pairing not found")

    if db_pairing.used_at is not None:
        raise HTTPException(status_code=400, detail="Token already used")

    if db_pairing.expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="Token expired")

    if db_pairing.balance_id is not None:
        if balance_id is not None and balance_id != db_pairing.balance_id:
            raise HTTPException(status_code=400, detail="Token does not belong to this balance")
        balance_id = db_pairing.balance_id
    elif balance_id is None:
        raise HTTPException(status_code=400, detail="balance_id is required for this token")

    if db.query(User).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")

    if db.query(Balance).filter(Balance.id == balance_id).first() is None:
        raise HTTPException(status_code=404, detail="Balance not found")

    already_paired = (
        db.query(UserBalanceAssociation)
        .filter(UserBalanceAssociation.user_id == user_id)
        .filter(UserBalanceAssociation.balance_id == balance_id)
        .first()
    )
    if already_paired is None:
        db.add(UserBalanceAssociation(user_id=user_id, balance_id=balance_id))

    db_pairing.used_at = datetime.now()
    db_pairing.user_id = user_id
    db_pairing.balance_id = balance_id
    db.commit()
    db.refresh(db_pairing)

    return ReturnModel(
        message="Scale already paired with this user" if already_paired else "Scale paired successfully",
        data={
            "pairing_id": db_pairing.id,
            "user_id": user_id,
            "balance_id": balance_id,
            "used_at": db_pairing.used_at,
        },
        success=True,
    )


@router.get("/pairing/{pairing_id}/status")
def pairing_status(
    pairing_id: int,
    db: DbDependency,
    poll_token: Annotated[Optional[str], Header(alias="X-Pairing-Token")] = None,
):
    """Estado do pareamento, consultado pela balança que gerou o QR Code.

    Exige o poll_token devolvido por /generate_qr_code/ (header
    X-Pairing-Token). ID inexistente e token errado respondem igual (404),
    para não revelar quais pareamentos existem. status:
      pending  - aguardando o app ler o QR Code
      expired  - não usado dentro da validade
      paired   - concluído e vínculo usuário/balança ativo (traz user_id)
      unpaired - concluído, mas o vínculo foi removido depois
    """
    if not poll_token:
        raise HTTPException(status_code=401, detail="Pairing token required")

    db_pairing = db.query(Pairing).filter(Pairing.id == pairing_id).first()
    if (
        db_pairing is None
        or db_pairing.poll_token_hash is None
        or not hmac.compare_digest(db_pairing.poll_token_hash, hash_pairing_secret(poll_token))
    ):
        raise HTTPException(status_code=404, detail="Pairing not found")

    user_id = None
    if db_pairing.used_at is not None and db_pairing.user_id is not None:
        active = (
            db.query(UserBalanceAssociation)
            .filter(UserBalanceAssociation.user_id == db_pairing.user_id)
            .filter(UserBalanceAssociation.balance_id == db_pairing.balance_id)
            .first()
            is not None
        )
        status = "paired" if active else "unpaired"
        user_id = db_pairing.user_id if active else None
    elif db_pairing.used_at is None and db_pairing.expires_at < datetime.now():
        status = "expired"
    else:
        status = "pending"

    return ReturnModel(
        message="Pairing status",
        data={
            "pairing_id": db_pairing.id,
            "status": status,
            "user_id": user_id,
            "balance_id": db_pairing.balance_id,
            "expires_at": db_pairing.expires_at,
        },
        success=True,
    )
