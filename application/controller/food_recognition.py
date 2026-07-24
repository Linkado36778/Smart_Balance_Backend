from fastapi import APIRouter, File, HTTPException, UploadFile

from SiglIp.test_01_Siglip import image_recognition_endpoint

router = APIRouter(tags=["food recognition"])


@router.post("/food-recognition/image")
async def recognize_food_from_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(status_code=400, detail="Empty image file.")

        return image_recognition_endpoint(contents)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
