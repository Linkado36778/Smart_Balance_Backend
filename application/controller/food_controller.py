"""Food search and meal management endpoints."""

from datetime import datetime, timedelta, timezone
import os
from typing import Annotated, Any, Dict, List, Optional, Union
from unicodedata import normalize

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.database import build_model_label, get_db
from application.models.application_models import Nutrient, Food, Brand, Category, Meal, User, Allergen, FoodNutrientAssociation, AllergenFoodAssociation, MealFoodAssociation, UserAllergenAssociation, DietFoodAssociation
from application.models.return_models import ReturnModel, ReturnException


#region Setup

router = APIRouter(tags=["Food"])
DbDependency = Annotated[Session, Depends(get_db)]
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")  # Default to localhost if not set

#region Schemas

class NutrientAmount(BaseModel):
    """TypedDict for nutrient amount input, allowing flexible formats."""
    id: int
    amount: float


class PostCreatedFoodBodyRequest(BaseModel):
    """Base model for food creation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    nutrients: List[NutrientAmount] = Field(default_factory=list)
    allergen_ids: List[int] = Field(default_factory=list)
    model_label: Optional[str] = None

    @field_validator("model_label")
    def clean_model_label(cls, value):
        """Treat blank prompts as absent."""
        if value is None:
            return None
        value = value.strip()
        return value or None


class PostCreateBrandBodyRequest(BaseModel):
    """Base model for brand creation."""
    name: str


class PostCreateMealBodyRequest(BaseModel):
    """Base model for meal creation."""
    model_config = ConfigDict(extra="forbid")

    name: str
    consumed_at: datetime
    # calories: float = 0.0
    # weight_g: float
    list_foods_ids: List[int] = Field(default_factory=list)
    list_foods_weights: List[float] = Field(default_factory=list)
    saved_meal: bool = False

    @field_validator("consumed_at", mode="before")
    def parse_consumed_at(cls, value):
        """Ensure consumed_at is a datetime object."""
        if isinstance(value, str) and len(value) <= 5 and ":" in value:
            try:
                return datetime.strptime(value, "%H:%M")
            except ValueError:
                raise ValueError("consumed_at must be in H:M format")
        return value

#region Helpers

def _load_local_timezone():
    """Fuso dos horarios gravados (horario de Brasilia, sem horario de verao desde 2019).

    A imagem python:slim nao traz tzdata; sem ele, usa o offset fixo -03:00.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Sao_Paulo")
    except Exception:  # ZoneInfoNotFoundError quando falta tzdata
        return timezone(timedelta(hours=-3))

LOCAL_TIMEZONE = _load_local_timezone()

# Clientes que enviam consumed_at SEM fuso (balanca/firmware) mandam o horario
# em UTC no POST /meals; ver commit 6e73391 (fix(UTCTime)).
NAIVE_UTC_OFFSET = timedelta(hours=3)

def to_local_consumed_at(value: datetime, naive_is_utc: bool) -> datetime:
    """Converte consumed_at para o horario local (naive) gravado no banco.

    - Com fuso (ex.: "2026-11-25T12:00:00-03:00", enviado pelo APP): converte
      para o horario de Brasilia, sem ajuste extra.
    - Sem fuso: mantem o comportamento anterior de cada rota. No POST /meals o
      valor e tratado como UTC (-3h, contrato atual da balanca); no PATCH e
      gravado como veio.
    """
    if value.tzinfo is not None:
        return value.astimezone(LOCAL_TIMEZONE).replace(tzinfo=None)
    return value - NAIVE_UTC_OFFSET if naive_is_utc else value

def calculate_meal_calories(db: Session, foods: List["Food"]) -> float:
    """Sum the calories of the given foods using their per-100g nutrient amounts."""
    total_calories = 0.0
    for food in foods:
        for nutrient, nutrient_amount in get_food_nutrients(db, food.id):
            amount_per_100g = parse_nutrient_amount(nutrient_amount, nutrient)
            total_calories += amount_per_100g * (nutrient.calories_per_unit or 0.0)
    return total_calories

def normalize_text(value: str) -> str:
    """Normalize text for consistent comparisons."""
    return normalize("NFKD", value.strip().lower()).encode("ascii", "ignore").decode("ascii")

def get_nutrient_by_identifier(db: Session, nutrient_identifier: Union[int, str]):
    """Fetch a nutrient by its ID or name. If a string is provided, it will be normalized for comparison."""
    if isinstance(nutrient_identifier, int):
        return db.query(Nutrient).filter(Nutrient.id == nutrient_identifier).first()

    if isinstance(nutrient_identifier, str) and nutrient_identifier.isdigit():
        return db.query(Nutrient).filter(Nutrient.id == int(nutrient_identifier)).first()

    normalized_identifier = normalize_text(nutrient_identifier)
    nutrients = db.query(Nutrient).all()
    return next(
        (n for n in nutrients if normalize_text(n.name) == normalized_identifier),
        None,
    )

def parse_nutrient_amount(value: Any, nutrient: Nutrient) -> float:
    """Parse nutrient amount from various formats, ensuring it returns a float."""
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        return float(value.replace(",", "."))

    if isinstance(value, dict):
        possible_keys = (
            str(nutrient.id),
            nutrient.name,
            normalize_text(nutrient.name),
            "amount",
            "value",
        )
        for key in possible_keys:
            if key in value:
                return parse_nutrient_amount(value[key], nutrient)

    if isinstance(value, list):
        if len(value) == 1:
            return parse_nutrient_amount(value[0], nutrient)

    return 0.0


def get_food_nutrients_by_weight(db: Session, food_id: int, weight: float):
    """Fetches the nutrients and their amounts for a given food item, adjusted for a specific weight."""
    food_nutrient = FoodNutrientAssociation.__table__

    # join Nutrient with the association table and return (Nutrient, amount)
    nutrients_with_amounts = (
        db.query(
            Nutrient,
            food_nutrient.c.amount,
        )
        .join(
            food_nutrient,
            Nutrient.id == food_nutrient.c.nutrient_id,
        )
        .filter(food_nutrient.c.food_id == food_id)
        .all()
    )

    return scale_nutrients_by_weight(nutrients_with_amounts, weight)


def scale_nutrients_by_weight(nutrients_with_amounts: List[Any], weight: float):
    """Scales (Nutrient, amount per 100g) pairs to the given weight."""
    # Adjust amounts based on the provided weight
    adjusted_nutrients = []
    for nutrient, amount in nutrients_with_amounts:
        adjusted_amount = (amount * weight) / 100.0  # Assuming the original amount is per 100g
        adjusted_nutrients.append((nutrient, adjusted_amount))

    return {
        "nutrients": [
            {
                "nutrient_id": nutrient.id,
                "name": nutrient.name,
                "amount": adjusted_amount,
                "unit": nutrient.unit
            }
            for nutrient, adjusted_amount in adjusted_nutrients
        ]
    }


def visible_to_user(user_id: int):
    """Filtro dos alimentos que o usuario enxerga: os globais e os criados por ele."""
    return or_(Food.user_id.is_(None), Food.user_id == user_id)


def get_visible_food(db: Session, food_id: int, user_id: int) -> Optional[Food]:
    """Busca um alimento global ou do proprio usuario (None se nao existir/nao for dele)."""
    return db.query(Food).filter(Food.id == food_id).filter(visible_to_user(user_id)).first()


def serialize_foods(db: Session, foods: List[Food], user_id: int) -> List[Dict[str, Any]]:
    """Formata alimentos com nutrientes e a flag de alergia do usuario."""
    food_ids = [food.id for food in foods]

    allergic_food_ids = {
        food_id
        for (food_id,) in (
            db.query(AllergenFoodAssociation.food_id)
            .join(
                UserAllergenAssociation,
                UserAllergenAssociation.allergen_id == AllergenFoodAssociation.allergen_id,
            )
            .filter(UserAllergenAssociation.user_id == user_id)
            .filter(AllergenFoodAssociation.food_id.in_(food_ids))
            .all()
        )
    }

    nutrients_by_food: Dict[int, List[Dict[str, Any]]] = {food_id: [] for food_id in food_ids}
    for nutrient, assoc in (
        db.query(Nutrient, FoodNutrientAssociation)
        .join(FoodNutrientAssociation, FoodNutrientAssociation.nutrient_id == Nutrient.id)
        .filter(FoodNutrientAssociation.food_id.in_(food_ids))
        .order_by(FoodNutrientAssociation.food_id, Nutrient.id)
        .all()
    ):
        nutrients_by_food[assoc.food_id].append({
            "id": nutrient.id,
            "name": nutrient.name,
            "amount": assoc.amount,
            "unit": nutrient.unit,
            "calories_per_unit": nutrient.calories_per_unit,
        })

    return [
        {
            "id": food.id,
            "name": food.name,
            "category_id": food.category_id,
            "brand_id": food.brand_id,
            "nutrients": nutrients_by_food[food.id],
            "image": f"{BASE_URL}/images/alimentos/{food.image_url}" if food.image_url else None,
            "user_allergic": food.id in allergic_food_ids,
            "description": food.description,
            "model_label": food.model_label,
            "created_by_user": food.user_id is not None,
        }
        for food in foods
    ]


def get_food_nutrients(db: Session, food_id: int) -> List[Any]:
    """Fetches the nutrients and their amounts for a given food item from the association table."""
    food_nutrient = FoodNutrientAssociation.__table__

    # join Nutrient with the association table and return (Nutrient, amount)
    return (
        db.query(
            Nutrient,
            food_nutrient.c.amount,
        )
        .join(
            food_nutrient,
            Nutrient.id == food_nutrient.c.nutrient_id,
        )
        .filter(food_nutrient.c.food_id == food_id)
        .all()
    )


def calculate_meal_totals(db: Session, meal: "PostCreateMealBodyRequest", user_id: int):
    """Validates the meal foods/weights and returns (foods, total_calories, total_nutrients),
    scaling each food's per-100g nutrient amounts to its consumed weight.

    Only global foods and foods created by the meal's user are accepted."""

    if not meal.list_foods_ids:
        raise HTTPException(status_code=400, detail="At least one food ID must be provided")

    if len(meal.list_foods_weights) != len(meal.list_foods_ids):
        raise HTTPException(
            status_code=400,
            detail="list_foods_weights must have the same length as list_foods_ids"
        )

    if any(weight <= 0 for weight in meal.list_foods_weights):
        raise HTTPException(status_code=400, detail="All food weights must be greater than zero")

    total_calories = 0.0
    total_nutrients: Dict[str, float] = {}
    foods: List[Food] = []

    for food_id, food_weight in zip(meal.list_foods_ids, meal.list_foods_weights):
        food = get_visible_food(db, food_id, user_id)

        if food is None:
            raise HTTPException(status_code=400, detail=f"Food_id: {food_id} dont exist")

        foods.append(food)

        for nutrient, nutrient_amount in get_food_nutrients(db, food.id):
            amount_per_100g = parse_nutrient_amount(nutrient_amount, nutrient)
            # Nutrient amounts are stored per 100g; scale them to the consumed weight
            adjusted_amount = amount_per_100g * food_weight / 100.0
            total_nutrients[nutrient.name] = total_nutrients.get(nutrient.name, 0.0) + adjusted_amount
            total_calories += adjusted_amount * (nutrient.calories_per_unit or 0.0)

    return foods, total_calories, total_nutrients

# Função integrada no list_foods para buscar os alérgenos do usuário para um alimento específico
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

#region Foods

@router.get("/foods")
def list_foods(db: DbDependency, user_id: int, name: Optional[str] = None):
    """Lista os alimentos globais e os criados pelo usuario (estes por ultimo),
    informando se o usuario e alergico a cada um."""

    if db.query(User).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Food).filter(visible_to_user(user_id))
    if name:
        query = query.filter(Food.name.ilike(f"%{name}%"))

    foods = query.order_by(Food.user_id.is_not(None), Food.id).all()
    return serialize_foods(db, foods, user_id)


@router.get("/foods/created")
def list_created_foods(db: DbDependency, user_id: int, name: Optional[str] = None):
    """Lista os alimentos criados pelo usuário e informa se ele e alergico a cada um."""

    if db.query(User).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Food).filter(Food.user_id == user_id)
    if name:
        query = query.filter(Food.name.ilike(f"%{name}%"))

    foods = query.order_by(Food.id).all()
    return serialize_foods(db, foods, user_id)


def set_food_associations(db: Session, food_id: int, body: PostCreatedFoodBodyRequest):
    """(Re)cria as associacoes de alergenos e nutrientes de um alimento."""
    db.query(FoodNutrientAssociation).filter(FoodNutrientAssociation.food_id == food_id).delete()
    db.query(AllergenFoodAssociation).filter(AllergenFoodAssociation.food_id == food_id).delete()

    for allergen_id in dict.fromkeys(body.allergen_ids):
        allergen = db.query(Allergen).filter(Allergen.id == allergen_id).first()

        if allergen is None:
            raise HTTPException(
                status_code=400,
                detail=f"Allergen with id '{allergen_id}' not found",
            )

        db.add(AllergenFoodAssociation(food_id=food_id, allergen_id=allergen.id))

    nutrient_ids = set()
    for nutrient_item in body.nutrients:
        nutrient = get_nutrient_by_identifier(db, nutrient_item.id)

        if nutrient is None:
            raise HTTPException(
                status_code=400,
                detail=f"Nutrient '{nutrient_item.id}' not found",
            )

        if nutrient.id in nutrient_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Nutrient '{nutrient_item.id}' informed more than once",
            )
        nutrient_ids.add(nutrient.id)

        db.add(FoodNutrientAssociation(food_id=food_id, nutrient_id=nutrient.id, amount=nutrient_item.amount))


def get_user_food_for_change(db: Session, food_id: int, user_id: int) -> Food:
    """Busca um alimento que o usuario pode editar/excluir (somente os criados por ele)."""
    food = db.query(Food).filter(Food.id == food_id).first()

    if food is None:
        raise HTTPException(status_code=404, detail="Food not found")

    if food.user_id is None:
        raise HTTPException(status_code=403, detail="Global foods cannot be changed")

    if food.user_id != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to change this food")

    return food


@router.post("/foods")
def create_food(body: PostCreatedFoodBodyRequest, db: DbDependency, user_id: int):
    """Cadastra um novo alimento do usuario com seus nutrientes."""
    try:
        if db.query(User).filter(User.id == user_id).first() is None:
            raise HTTPException(status_code=404, detail="User not found")

        existing = (
            db.query(Food)
            .filter(Food.user_id == user_id)
            .filter(func.lower(Food.name) == body.name.strip().lower())
            .first()
        )

        if existing is not None:
            raise HTTPException(status_code=400, detail="Food already exists")

        new_food = Food(
            name=body.name.strip(),
            category_id=body.category_id,
            brand_id=body.brand_id,
            model_label=build_model_label(body.name, body.model_label),
            user_id=user_id,
        )

        db.add(new_food)
        db.flush()

        set_food_associations(db, new_food.id, body)

        db.commit()
        db.refresh(new_food)

        return ReturnModel(
            message="Food created successfully",
            data=None,
            success=True
        )

    except (HTTPException, IntegrityError):
        db.rollback()
        raise
    except Exception as err:
        db.rollback()
        raise ReturnException(
            message=str(err),
            success=False,
        ) from err


@router.patch("/foods/{food_id}")
def update_food(food_id: int, food: PostCreatedFoodBodyRequest, db: DbDependency, user_id: int):
    """Atualiza um alimento criado pelo usuario com seus nutrientes."""
    try:
        existing_food = get_user_food_for_change(db, food_id, user_id)

        duplicate = (
            db.query(Food)
            .filter(Food.user_id == user_id)
            .filter(Food.id != food_id)
            .filter(func.lower(Food.name) == food.name.strip().lower())
            .first()
        )
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="Food already exists")

        existing_food.name = food.name.strip()
        existing_food.category_id = food.category_id
        existing_food.brand_id = food.brand_id
        existing_food.model_label = build_model_label(food.name, food.model_label)

        set_food_associations(db, existing_food.id, food)

        db.commit()
        db.refresh(existing_food)

        return ReturnModel(
            message="Food updated successfully",
            data=existing_food,
            success=True
        )

    except (HTTPException, IntegrityError):
        db.rollback()
        raise
    except Exception as err:
        db.rollback()
        raise ReturnException(
            message=str(err),
            success=False,
        ) from err


@router.delete("/foods/{food_id}")
def delete_food(food_id: int, db: DbDependency, user_id: int):
    """Deleta um alimento criado pelo usuario.

    Alimentos usados em refeicoes ou dietas nao sao excluidos (409), para nao
    alterar o historico dessas refeicoes/dietas.
    """
    try:
        existing_food = get_user_food_for_change(db, food_id, user_id)

        in_use = (
            db.query(MealFoodAssociation).filter(MealFoodAssociation.food_id == food_id).first()
            or db.query(DietFoodAssociation).filter(DietFoodAssociation.food_id == food_id).first()
        )
        if in_use is not None:
            raise HTTPException(status_code=409, detail="Food is used in meals or diets and cannot be deleted")

        db.query(FoodNutrientAssociation).filter(FoodNutrientAssociation.food_id == food_id).delete()
        db.query(AllergenFoodAssociation).filter(AllergenFoodAssociation.food_id == food_id).delete()

        db.delete(existing_food)
        db.commit()

        return ReturnModel(
            message="Food deleted successfully",
            success=True
        )

    except (HTTPException, IntegrityError):
        db.rollback()
        raise
    except Exception as err:
        db.rollback()
        raise ReturnException(
            message=str(err),
            success=False,
        ) from err

#region Brands

@router.get(
    "/brands",
    responses={
        200: {"model": ReturnModel[Brand], "description": "Brands getted successfully"},
    }
)
def search_brands(query_brand_name: str, db: DbDependency):
    """Busca marcas pelo nome (parcial)."""
    brands = db.query(Brand).filter(Brand.name.ilike(f"%{query_brand_name}%")).all()

    if brands is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    return ReturnModel(
        message="Brands getted successfully",
        data=brands,
        success=True
    )

@router.patch("/brands/{brand_id}")
def update_brand(brand_id: int, brand: PostCreateBrandBodyRequest, db: DbDependency):
    """Atualiza uma marca existente."""
    existing_brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if existing_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    existing_brand.name = brand.name
    db.commit()
    db.refresh(existing_brand)
    return existing_brand

@router.delete("/brands/{brand_id}")
def delete_brand(brand_id: int, db: DbDependency):
    """Deleta uma marca existente."""
    existing_brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if existing_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    db.delete(existing_brand)
    db.commit()
    return {"message": "Brand deleted successfully"}

@router.post(
    "/brands",
    responses={
        200: {"model": ReturnModel, "description": "Brands created successfully"},
    }
)
def create_brand(body: PostCreateBrandBodyRequest, db: DbDependency):
    """Cadastra uma nova marca."""
    existing = db.query(Brand).filter(func.lower(Brand.name) == body.name.strip().lower()).first()

    if existing is not None:
        raise HTTPException(status_code=400, detail="Brand already exists")

    new_brand = Brand(
        name=body.name
    )

    db.add(new_brand)
    db.commit()
    db.refresh(new_brand)

    return ReturnModel(
        message="Brands created successfully",
        data=None,
        success=True
    )

#region Categories

@router.get(
    "/categories",
    responses={
        200: {"model": ReturnModel[Category], "description": "Categories getted successfully"},
    }
)
def list_categories(db: DbDependency):
    """Lista todas as categorias de alimentos."""
    return ReturnModel(
        message="Categories getted successfully",
        data=db.query(Category).order_by(Category.id).all(),
        success=True
    )

#region Nutrients

@router.get(
    "/nutrients",
    responses={
        200: {"model": ReturnModel[Nutrient], "description": "Nutrients getted successfully"},
    }
)
def list_nutrients(db: DbDependency):
    """Lista todos os nutrientes disponíveis."""
    return ReturnModel(
        message="Nutrients getted successfully",
        data=db.query(Nutrient).order_by(Nutrient.id).all(),
        success=True
    )

@router.get("/nutrients/{food_id}")
def list_micro_nutrients(food_id: int, db: DbDependency):
    """Lista todos os nutrientes disponíveis."""
    return db.query(FoodNutrientAssociation).join(Nutrient).filter(
        (Nutrient.name != "Proteinas") &
        (Nutrient.name != "Carboidratos") &
        (Nutrient.name != "Gorduras")
    ).filter(
        FoodNutrientAssociation.food_id == food_id
    ).all()

#region Meals

@router.get("/meals")
def list_user_meals(user_id: int, db: DbDependency):
    """Busca uma refeição pelo ID do usuário."""
    meals = db.query(Meal).filter(Meal.user_id == user_id).all()
    if not meals:
        raise HTTPException(status_code=404, detail="Meal not found")
    result = []
    for meal in meals:
        # Each food is paired with ITS OWN weight from the same association row
        foods_with_weights = (
            db.query(Food, MealFoodAssociation.food_weight_g)
            .join(MealFoodAssociation, MealFoodAssociation.food_id == Food.id)
            .filter(MealFoodAssociation.meal_id == meal.id)
            .all()
        )

        result.append({
            "id": meal.id,
            "name": meal.name,
            "calories": meal.calories,
            "weight_g": meal.weight_g,
            "consumed_at": meal.consumed_at,
            "user_id": meal.user_id,
            "foods": [
                {
                    "id": food.id,
                    "name": food.name,
                    "category_id": food.category_id,
                    "brand_id": food.brand_id,
                    "weight_g": food_weight_g,
                    "image": f"{BASE_URL}/images/alimentos/{food.image_url}" if food.image_url else None,
                    "created_by_user": food.user_id is not None,
                }
                for food, food_weight_g in foods_with_weights
            ],
        })
    return result


@router.post(
    "/meals",
    responses={
        200: {"model": ReturnModel, "description": "Meal created successfully"},
    }
)
def create_meal(meal: PostCreateMealBodyRequest, db: DbDependency, user_id: int):
    """Calcula calorias/nutrientes e cadastra uma refeição."""

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=400, detail=f"User_id: {user_id} dont exist")

    foods, total_calories, _ = calculate_meal_totals(db, meal, user.id)

    total_weight = sum(meal.list_foods_weights)

    new_meal = Meal(
        name = meal.name,
        user_id = user.id,
        consumed_at = to_local_consumed_at(meal.consumed_at, naive_is_utc=True),
        calories = total_calories,
        weight_g = total_weight,
        saved_meal = meal.saved_meal
    )

    if new_meal.weight_g <= 0:
        raise HTTPException(status_code=400, detail="Invalid meal weight")

    if new_meal.saved_meal == True:
        db.add(new_meal)
        db.flush()

        for weight, food in zip(meal.list_foods_weights, foods):
            assoc = MealFoodAssociation(
                meal_id=new_meal.id,
                food_id=food.id,
                food_weight_g=weight
            )
            db.add(assoc)

        db.commit()
        db.refresh(new_meal)

    return new_meal


@router.patch("/meals/{meal_id}/{user_id}", responses={200: {"model": Meal, "description": "Meal updated successfully"}})
def update_meal(meal_id: int, user_id: int, meal: PostCreateMealBodyRequest, db: DbDependency):
    """Atualiza uma refeição existente."""

    updated_meal = db.query(Meal).filter(Meal.id == meal_id).filter(Meal.user_id == user_id).first()

    if not updated_meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    total_weight = sum(meal.list_foods_weights)
    if total_weight <= 0:
        raise HTTPException(status_code=400, detail="Invalid meal weight")

    # Validate and recalculate before touching the database
    foods, total_calories, _ = calculate_meal_totals(db, meal, user_id)

    updated_meal.name = meal.name
    updated_meal.consumed_at = to_local_consumed_at(meal.consumed_at, naive_is_utc=False)
    updated_meal.calories = total_calories
    updated_meal.weight_g = total_weight
    updated_meal.saved_meal = meal.saved_meal

    db.query(MealFoodAssociation).filter(MealFoodAssociation.meal_id == updated_meal.id).delete()

    for food, food_weight in zip(foods, meal.list_foods_weights):
        db.add(MealFoodAssociation(
            meal_id=updated_meal.id,
            food_id=food.id,
            food_weight_g=food_weight
        ))

    db.commit()
    db.refresh(updated_meal)
    return updated_meal

@router.delete("/meals/{meal_id}/{user_id}", responses={200: {"model": Meal, "description": "Meal deleted successfully"}})
def delete_meal(meal_id: int, user_id: int, db: DbDependency):
    """Deleta uma refeição existente."""

    meal_to_delete = db.query(Meal).filter(Meal.id == meal_id).filter(Meal.user_id == user_id).first()

    if not meal_to_delete:
        raise HTTPException(status_code=404, detail="Meal not found")

    db.query(MealFoodAssociation).filter(MealFoodAssociation.meal_id == meal_to_delete.id).delete()

    db.delete(meal_to_delete)
    db.commit()
    return {"message": "Meal deleted successfully"}
