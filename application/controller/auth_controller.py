"""Controller for authentication management"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from shared.database import get_db
from application.models.application_models import User, Nutricionist
from application.models.return_models import ReturnModel, ReturnException


#region Setup

router = APIRouter(tags=["Auth"])
DbDependency = Annotated[Session, Depends(get_db)]
password_hash = PasswordHash.recommended()

#region Schemas

class PostAuthUserBodyRequest(BaseModel):
    """Body request model for auth a user"""
    email: str
    password: str

#region User

@router.post(
    "/auth/commun_user",
    responses = {
        200: {"model": ReturnModel, "description": "User authenticated successfully"},
    }
)
def auth_user(body: PostAuthUserBodyRequest, db: DbDependency):
    """Endpoint to authenticated commun user"""
    try: 
        user = db.query(User).filter(User.email == body.email).first()

        if user is None:
            raise ReturnException(
                message="Credencial inválida",
                status_code=status.HTTP_401_UNAUTHORIZED,
                success=False,
            )
        
        is_correct, updated_hash = password_hash.verify_and_update(body.password, user.password)
        
        if is_correct:
            if updated_hash is not None:
                db.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(password=updated_hash)
                )
                db.commit()
            
            return ReturnModel(
                message="User authenticated successfully",
                data=None,
                success=True
            )
        
        raise ReturnException(
            message="Credencial inválida",
            status_code=status.HTTP_401_UNAUTHORIZED,
            success=False,
        )

    except Exception as err:
        db.rollback()
        raise ReturnException(
            message=str(err),
            success=False,
        ) from err

#region Nutricionist

@router.post(
    "/auth/nutricionist",
    responses = {
        200: {"model": ReturnModel, "description": "Nutricionist authenticated successfully"},
    }
)
def auth_nutricionist(body: PostAuthUserBodyRequest, db: DbDependency):
    """Endpoint to authenticated nutricionist"""
    try: 
        nutricionist = db.query(Nutricionist).filter(Nutricionist.email == body.email).first()

        if nutricionist is None:
            raise ReturnException(
                message="Credencial inválida",
                status_code=status.HTTP_401_UNAUTHORIZED,
                success=False,
            )
        
        is_correct, updated_hash = password_hash.verify_and_update(body.password, nutricionist.password)
        
        if is_correct:
            if updated_hash is not None:
                db.execute(
                    update(Nutricionist)
                    .where(Nutricionist.id == nutricionist.id)
                    .values(password=updated_hash)
                )
                db.commit()
            
            return ReturnModel(
                message="Nutricionist authenticated successfully",
                data=None,
                success=True
            )
        
        raise ReturnException(
            message="Credencial inválida",
            status_code=status.HTTP_401_UNAUTHORIZED,
            success=False,
        )

    except Exception as err:
        db.rollback()
        raise ReturnException(
            message=str(err),
            success=False,
        ) from err
