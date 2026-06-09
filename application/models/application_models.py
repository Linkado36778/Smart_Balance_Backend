from shared.database import Base
from sqlalchemy import DateTime, Boolean, Float, Date, Integer, Column, String, ForeignKey, JSON, Table
from sqlalchemy.orm import relationship

# Association tables for many-to-many relationships
user_allergen_association = Table(
    'Usuario_Alergeno',
    Base.metadata,
    Column('allergen_id_FK1', Integer, ForeignKey('Alergeno.allergen_id'), primary_key=True),
    Column('user_id_FK1', Integer, ForeignKey('Usuario.user_id'), primary_key=True)
)

meal_food_association = Table(
    'Refeicao_Alimento',
    Base.metadata,
    Column('food_id_FK', Integer, ForeignKey('Alimento.food_id'), primary_key=True),
    Column('meal_id_FK', Integer, ForeignKey('Refeicao.meal_id'))
)

food_nutrient_association = Table(
    'Alimento_Nutriente',
    Base.metadata,
    Column('nutrient_id_FK', Integer, ForeignKey('Nutriente.nutrient_id'), primary_key=True),
    Column('food_id_FK1', Integer, ForeignKey('Alimento.food_id'))
)

allergen_food_association = Table(
    'Alergeno_Alimento',
    Base.metadata,
    Column('food_id_FK2', Integer, ForeignKey('Alimento.food_id'), primary_key=True),
    Column('allergen_id_FK2', Integer, ForeignKey('Alergeno.allergen_id'), primary_key=True)
)

class Nutricionist(Base):
    __tablename__ = "Nutricionista"

    nutricionist_id = Column(Integer, primary_key=True, index=True)
    nutricionist_password = Column(String, index=True)
    nutricionist_created_at = Column(DateTime, index=True)
    nutricionist_phone = Column(String, index=True)
    nutricionist_email = Column(String, index=True) 

class Allergen(Base):
    __tablename__ = "Alergeno"

    allergen_id = Column(Integer, primary_key=True, index=True)
    allergen_name = Column(String, index=True)

    #Relationships
    allergen_user_rl = relationship("User", secondary=user_allergen_association, back_populates="user_allergen_rl")
    allergen_food_rl = relationship("Food", secondary=allergen_food_association, back_populates="food_allergen_rl")


class User(Base):
    __tablename__ = "Usuario"
    user_id = Column(Integer, primary_key=True, index=True)
    user_password = Column(String, index=True)
    user_email = Column(String, index=True)
    user_birthdate = Column(Date, index=True)
    user_weight_kg = Column(Float, index=True)
    user_height_m = Column(Float, index=True)
    user_sex = Column(Boolean, index=True)
    user_created_at = Column(DateTime, index=True)
    nutricionist_id_FK = Column(Integer, index=True)

    #Relationships
    user_allergen_rl = relationship("Allergen", secondary=user_allergen_association, back_populates="allergen_user_rl")
    user_meal_rl = relationship("Meal", back_populates="meal_user_rl")


class Meal(Base):
    __tablename__ = "Refeicao"

    meal_id = Column(Integer, primary_key=True, index=True)
    meal_name = Column(String, index=True)
    meal_items = Column(JSON)
    meal_calories = Column(Float, index=True)
    meal_nutrients = Column(JSON)
    weight_g = Column(Float, index=True)   
    consumed_at = Column(Date, index=True)
    user_id_FK2 = Column(Integer, ForeignKey("Usuario.user_id"), index=True)

    #Relationships
    meal_user_rl = relationship("User", back_populates="user_meal_rl", uselist=False)
    meal_food_rl = relationship("Food", secondary=meal_food_association, back_populates="food_meal_rl")


class Food(Base):
    __tablename__ = "Alimento"

    food_id = Column(Integer, primary_key=True, index=True)
    food_name = Column(String, index=True)
    category_name = Column(String, index=True)
    food_calories = Column(Float, index=True)
    food_weight_g_ml = Column(Float, index=True)
    food_nutrient_type = Column(JSON)
    food_nutrient_amount = Column(JSON)
    brand_id_FK = Column(Integer, ForeignKey("Marca.brand_id"), index=True)

    #Relationships
    food_meal_rl = relationship("Meal", secondary=meal_food_association, back_populates="meal_food_rl")
    food_brand_rl = relationship("Brand", back_populates="brand_food_rl", uselist=False)
    food_nutrient_rl = relationship("Nutrient", secondary=food_nutrient_association, back_populates="nutrient_food_rl")
    food_allergen_rl = relationship("Allergen", secondary=allergen_food_association, back_populates="allergen_food_rl")


class Brand(Base):
    __tablename__ = "Marca"

    brand_id = Column(Integer, primary_key=True, index=True)
    brand_name = Column(String, index=True)

    #Relationships
    brand_food_rl = relationship("Food", back_populates="food_brand_rl")


class Nutrient(Base):
    __tablename__ = "Nutriente"

    nutrient_id = Column(Integer, primary_key=True, index=True)
    nutrient_name = Column(String, index=True)
    nutrient_unit = Column(String, index=True)

    #Realtionships
    nutrient_food_rl = relationship("Food", secondary=food_nutrient_association, back_populates="food_nutrient_rl")
