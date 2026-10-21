"""Controller for user management, including user and nutricionist creation and retrieval."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from pwdlib import PasswordHash
from urllib.parse import urlencode

from shared.database import get_db
from application.models.application_models import Allergen, Balance, Diet, DietFoodAssociation, Food, MealFoodAssociation, User, Nutricionist, UserAllergenAssociation, Pairing, UserBalanceAssociation
from application.models.return_model import ReturnModel
import re
import secrets
import hashlib
import qrcode
import os

BASE_URL = os.environ.get("BASE_URL") or "http://localhost:8000"
QR_CODES_DIR = Path(__file__).resolve().parents[2] / "qr_codes"

router = APIRouter(prefix="/users", tags=["users"])
password_hash = PasswordHash.recommended()

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
    goal: str

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

@router.post("/create_diet/{nutricionist_id}/{user_id}")
def create_diet(user_id: int, nutricionist_id: int, db: DbDependency, diet: PostCreateDietBodyRequest):
    """Create a diet for a user, linked to a nutricionist."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_nutricionist = db.query(Nutricionist).filter(Nutricionist.id == nutricionist_id).first()
    if db_nutricionist is None:
        raise HTTPException(status_code=404, detail="Nutricionist not found")

    new_diet = Diet(
        name = diet.name,
        user_id = diet.user_id,
        nutricionist_id = diet.nutricionist_id,
        goal = diet.goal
    )

    db.add(new_diet)
    db.flush()

    foods: List[Food] = []
    
    for food_id in diet.list_foods_ids:
        food = db.query(Food).filter(Food.id == food_id).first()
        
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


@router.post("/generate_qr_code/{balance_id}/{user_id}")
def generate_qr_code(balance_id: int, user_id: int,db: DbDependency):
    """Cria um token temporário e devolve seu QR Code."""

    db_balance = (
        db.query(Balance)
        .filter(Balance.id == balance_id)
        .first()
    )

    if db_balance is None:
        raise HTTPException(status_code=404, detail="Balance not found")

    db_user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    pairing_token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        pairing_token.encode("utf-8")
    ).hexdigest()

    db_pairing = Pairing(
        token_hash=token_hash,
        expires_at=datetime.now() + timedelta(minutes=5),
        used_at=None,
    )

    db.add(db_pairing)
    db.commit()
    db.refresh(db_pairing)

    query_string = urlencode({"token": pairing_token})
    balance_query_string = urlencode({"balance_id": balance_id})
    user_query_string = urlencode({"user_id": user_id})
    pairing_url = f"{BASE_URL}/users/pair-scale?{user_query_string}&{balance_query_string}&{query_string}"

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
            "qr_code_url": qr_code_url,
        },
        success=True,
    )

@router.get("/pair-scale")
def pair_scale(user_id: int, balance_id: int, token: str, db: DbDependency):
    """Endpoint to pair a scale using a token from the QR code."""

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    db_pairing = (
        db.query(Pairing)
        .filter(Pairing.token_hash == token_hash)
        .first()
    )

    if db_pairing is None:
        raise HTTPException(status_code=404, detail="Pairing not found")

    if db_pairing.used_at is not None:
        raise HTTPException(status_code=400, detail="Token already used")

    if db_pairing.expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="Token expired")

    associated_balance = (
        UserBalanceAssociation(
            user_id=user_id,
            balance_id=balance_id
    )
    )

    db.add(associated_balance)

    db_pairing.used_at = datetime.now()
    db.commit()
    db.refresh(db_pairing)

    return ReturnModel(
        message="Scale paired successfully",
        data={
            "pairing_id": db_pairing.id,
            "user_id": user_id,
            "balance_id": balance_id,
            "used_at": db_pairing.used_at,
        },
        success=True,
    )
