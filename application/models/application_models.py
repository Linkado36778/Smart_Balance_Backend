"""Module provides SQLAlchemy models for the application."""

from typing import Optional
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, DeclarativeBase, MappedAsDataclass, mapped_column

# pylint: disable=unsubscriptable-object
# pylint: disable=too-few-public-methods


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for SQLAlchemy models, combining dataclass features with declarative mapping."""


class UserAllergenAssociation(Base):
    """Resolution table Many-to-Many User, Allergen."""

    __tablename__ = 'User_Allergen'

    allergen_id: Mapped[int] = mapped_column(
        ForeignKey('Allergen.id', ondelete="CASCADE"),
        primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey('User.id', ondelete="CASCADE"),
        primary_key=True
    )


class MealFoodAssociation(Base):
    """Resolution table Many-to-Many Meal, Food."""

    __tablename__ = 'Meal_Food'

    meal_id: Mapped[int] = mapped_column(
        ForeignKey('Meal.id', ondelete="CASCADE"),
        primary_key=True
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey('Food.id', ondelete="CASCADE"),
        primary_key=True
    )


class FoodNutrientAssociation(Base):
    """Resolution table Many-to-Many Food, Nutrient."""

    __tablename__ = 'Food_Nutrient'

    food_id: Mapped[int] = mapped_column(
        ForeignKey('Food.id', ondelete="CASCADE"),
        primary_key=True
    )
    nutrient_id: Mapped[int] = mapped_column(
        ForeignKey('Nutrient.id', ondelete="CASCADE"),
        primary_key=True
    )
    amount: Mapped[float] = mapped_column()


class AllergenFoodAssociation(Base):
    """Resolution table Many-to-Many Allergen, Food."""

    __tablename__ = 'Allergen_Food'

    food_id: Mapped[int] = mapped_column(
        ForeignKey('Food.id', ondelete="CASCADE"),
        primary_key=True
    )
    allergen_id: Mapped[int] = mapped_column(
        ForeignKey('Allergen.id', ondelete="CASCADE"),
        primary_key=True
    )


class Nutricionist(Base):
    """Model representing a nutritionist in the application."""

    __tablename__ = "Nutricionist"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, init=False)
    password: Mapped[str] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(index=True)
    phone: Mapped[str] = mapped_column(index=True)
    email: Mapped[str] = mapped_column(index=True)


class User(Base):
    """Model representing a user in the application."""

    __tablename__ = "User"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, init=False)
    password: Mapped[str] = mapped_column()
    email: Mapped[str] = mapped_column(index=True)
    birthdate: Mapped[datetime] = mapped_column()
    weight_kg: Mapped[float] = mapped_column()
    height_m: Mapped[float] = mapped_column()
    sex: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column()
    is_active: Mapped[bool] = mapped_column()
    nutricionist_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Nutricionist.id"), index=True, default=None
    )


class Meal(Base):
    """Model representing a meal in the application."""

    __tablename__ = "Meal"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, init=False)
    name: Mapped[str] = mapped_column()
    calories: Mapped[float] = mapped_column()
    weight_g: Mapped[float] = mapped_column()
    consumed_at_date: Mapped[datetime] = mapped_column()
    consumed_at_time: Mapped[datetime] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey("User.id"), index=True)


class Food(Base):
    """Model representing a food item in the application."""

    __tablename__ = "Food"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, init=False)
    name: Mapped[str] = mapped_column(index=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Category.id"), index=True, default=None
    )
    brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Brand.id"), index=True, default=None
    )


class Brand(Base):
    """Model representing a food brand in the application."""

    __tablename__ = "Brand"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, init=False)
    name: Mapped[str] = mapped_column(index=True)


class Nutrient(Base):
    """Model representing a nutrient in the application."""

    __tablename__ = "Nutrient"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, init=False)
    name: Mapped[str] = mapped_column(index=True)
    unit: Mapped[str] = mapped_column(index=True)
    calories_per_unit: Mapped[Optional[float]] = mapped_column(index=True, default=0.0)


class Category(Base):
    """Model representing a food category in the application."""

    __tablename__ = "Category"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, init=False)
    name: Mapped[str] = mapped_column(index=True)


class Allergen(Base):
    """Model representing an allergen in the application."""

    __tablename__ = "Allergen"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, init=False)
    name: Mapped[str] = mapped_column(index=True)
