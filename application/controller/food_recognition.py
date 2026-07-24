from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from SiglIp.test_01_Siglip import image_recognition_endpoint
from shared.database import get_db

router = APIRouter(tags=["food recognition"])
DbDependency = Annotated[Session, Depends(get_db)]


@router.post("/food-recognition/image")
async def recognize_food_from_image(db: DbDependency, file: UploadFile = File(...)):
    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(status_code=400, detail="Empty image file.")

        return image_recognition_endpoint(contents, db)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
