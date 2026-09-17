from typing import Annotated
from pathlib import Path
from application.models.application_models import User
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
import shutil

from SiglIp.test_01_Siglip import image_recognition_endpoint, recognize_changed_foods
from shared.database import get_db

router = APIRouter(tags=["food recognition"])
DbDependency = Annotated[Session, Depends(get_db)]

previous_images: dict[int, str] = {}

def save_temp_image(user_id: int, contents: bytes) -> str:
    temp_dir = Path("tmp/food_recognition")
    temp_dir.mkdir(parents=True, exist_ok=True)
    count = len(list(temp_dir.glob(f"user_{user_id}_*.jpg"))) + 1

    filename = f"user_{user_id}_{count}.jpg"
    image_path = temp_dir / filename

    with open(image_path, "wb") as file:
        file.write(contents)

    return str(image_path)


def get_previous_image_path(user_id: int) -> str | None:
    return previous_images.get(user_id)


def set_previous_image_path(user_id: int, image_path: str):
    previous_images[user_id] = image_path


@router.post("/food-recognition/image")
async def recognize_food_from_image(user_id: int, db: DbDependency, file: UploadFile = File(...)):

    db_user = db.query(User).filter(User.id == user_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(status_code=400, detail="Empty image file.")

        previous_path = get_previous_image_path(user_id)
        current_path = save_temp_image(user_id, contents)

        if previous_path:
            result = recognize_changed_foods(previous_path, current_path, db)
        else:
            recognition = image_recognition_endpoint(contents, db)

            result = {
                "changed": False,
                "first_image": True,
                "items": [
                    {
                        "bbox": None,
                        "recognized_food": recognition,
                    }
                ],
            }

        set_previous_image_path(user_id, current_path)

        return result
    
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.on_event("shutdown")
def shutdown_event():
    for folder in ["tmp", "output"]:
        path = Path(folder)
        if path.exists():
            shutil.rmtree(path)