"""Module provides SQLAlchemy models for the application."""

import dataclasses
from shared.database import Base
from sqlalchemy import DateTime, Boolean, Float, Date, Integer, Column, String, ForeignKey, Table
from sqlalchemy.orm import relationship

# Association tables for many-to-many relationships
user_allergen_association = Table(
    'User_Allergen',
    Base.metadata,
    Column('allergen_id', Integer, ForeignKey('Allergen.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('User.id'), primary_key=True)
)

meal_food_association = Table(
    'Meal_Food',
    Base.metadata,
    Column('food_id', Integer, ForeignKey('Food.id'), primary_key=True),
    Column('meal_id', Integer, ForeignKey('Meal.id'))
)

food_nutrient_association = Table(
    'Food_Nutrient',
    Base.metadata,
    Column('nutrient_id', Integer, ForeignKey('Nutrient.id'), primary_key=True),
    Column('food_id', Integer, ForeignKey('Food.id'), primary_key=True),
    Column('amount', Integer)
)

allergen_food_association = Table(
    'Allergen_Food',
    Base.metadata,
    Column('food_id', Integer, ForeignKey('Food.id'), primary_key=True),
    Column('allergen_id', Integer, ForeignKey('Allergen.id'), primary_key=True)
)

@dataclasses.dataclass
class Nutricionist(Base):
    """Model representing a nutritionist in the application."""

    __tablename__ = "Nutricionist"

    id = Column(Integer, primary_key=True, index=True)
    password = Column(String, index=True)
    created_at = Column(DateTime, index=True)
    phone = Column(String, index=True)
    email = Column(String, index=True)

@dataclasses.dataclass
class Allergen(Base):
    """Model representing an allergen in the application."""

    __tablename__ = "Allergen"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)

    #Relationships
    user_rl = relationship("User", secondary=user_allergen_association, back_populates="allergen_rl")
    food_rl = relationship("Food", secondary=allergen_food_association, back_populates="allergen_rl")


@dataclasses.dataclass
class User(Base):
    """Model representing a user in the application."""

    __tablename__ = "User"
    id = Column(Integer, primary_key=True, index=True)
    password = Column(String, index=True)
    email = Column(String, index=True)
    birthdate = Column(Date, index=True)
    weight_kg = Column(Float, index=True)
    height_m = Column(Float, index=True)
    sex = Column(String, index=True)
    created_at = Column(DateTime, index=True)
    is_active = Column(Boolean, index=True)
    nutricionist_id = Column(Integer, ForeignKey("Nutricionist.id"), index=True, nullable=True)

    #Relationships
    allergen_rl = relationship("Allergen", secondary=user_allergen_association, back_populates="user_rl")
    meal_rl = relationship("Meal", back_populates="user_rl")


@dataclasses.dataclass
class Meal(Base):
    """Model representing a meal in the application."""
    __tablename__ = "Meal"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    calories = Column(Float, index=True)
    nutrients = Column(Float, index=True)
    weight_g = Column(Float, index=True)
    consumed_at_date = Column(String, index=True)
    consumed_at_time = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("User.id"), index=True)

    #Relationships
    user_rl = relationship("User", back_populates="meal_rl", uselist=False)
    food_rl = relationship("Food", secondary=meal_food_association, back_populates="meal_rl")


@dataclasses.dataclass
class Food(Base):
    """Model representing a food item in the application."""
    __tablename__ = "Food"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category_id = Column(Integer, ForeignKey("Category.id"), index=True, nullable=True)
    brand_id = Column(Integer, ForeignKey("Brand.id"), index=True, nullable=True)

    #Relationships
    meal_rl = relationship("Meal", secondary=meal_food_association, back_populates="food_rl")
    brand_rl = relationship("Brand", back_populates="food_rl", uselist=False)
    category_rl = relationship("Category", back_populates="food_rl", uselist=False)
    nutrient_rl = relationship("Nutrient", secondary=food_nutrient_association, back_populates="food_rl")
    allergen_rl = relationship("Allergen", secondary=allergen_food_association, back_populates="food_rl")

@dataclasses.dataclass
class Brand(Base):
    """Model representing a food brand in the application."""
    __tablename__ = "Brand"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)

    #Relationships
    food_rl = relationship("Food", back_populates="brand_rl")

@dataclasses.dataclass
class Nutrient(Base):
    """Model representing a nutrient in the application."""
    __tablename__ = "Nutrient"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    unit = Column(String, index=True)
    calories_per_unit = Column(Float, index=True, default=0.0)

    #Relationships
    food_rl = relationship("Food", secondary=food_nutrient_association, back_populates="nutrient_rl")

@dataclasses.dataclass
class Category(Base):
    """Model representing a food category in the application."""
    __tablename__ = "Category"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)

    #Relationships
    food_rl = relationship("Food", back_populates="category_rl")
