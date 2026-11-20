"""Controller for vision recognition management"""

import os
from typing import Annotated

from fastapi import APIRouter, UploadFile, Depends, File
from sqlalchemy.orm import Session

from shared.database import get_db
from application.models.return_models import ReturnModel, ReturnException, ReturnSuccessSaveImageModel

#region Setup

router = APIRouter(tags=["Vision Recognition"])
DbDependency = Annotated[Session, Depends(get_db)]
UPLOAD_DIR = "static/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

#region Update Image

@router.post(
    "/upload-image",
    responses={
        200: {"model": ReturnModel, "description": "Image saved successfully"},
        400: {"model": ReturnException}
    }
)
async def save_image(file: UploadFile = File(...), category: str | None = None):
    """Endpoint to save a dataset image"""

    if not file.content_type:
        raise ReturnException(
            message="content_type not available.",
        )

    # 1. Validate that the file is actually an image
    if not file.content_type.startswith("image/"):
        raise ReturnException(
            message="File provided is not an image.",
        )
    
    # 2. Define the absolute destination file path
    if category:
        os.makedirs(F"{UPLOAD_DIR}/{category}", exist_ok=True)
        file_path = os.path.join(F"{UPLOAD_DIR}/{category}/{str(file.filename)}")
    else:
        file_path = os.path.join(F"{UPLOAD_DIR}/{str(file.filename)}")
    
    # 3. Read the uploaded file data and write it to disk
    try:
        file_content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
    except Exception as err:
        raise ReturnException(
            message=str(err),
        ) from err

    finally:
        await file.close() # Clean up resource memory

    return ReturnModel(
        message="Image saved successfully",
        data=ReturnSuccessSaveImageModel(
            filename = str(file.filename),
            saved_path = file_path
        ),
        success=True
    )
