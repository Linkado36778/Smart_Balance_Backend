from fastapi import FastAPI, HTTPException, UploadFile, File
import base64

app = FastAPI()

@app.post("/image_to_byte")
async def image_recognition_endpoint(bytes: str):
    try:
        return {"image_b64": bytes}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
async def image_to_byte_endpoint(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        byte_data = base64.b64encode(contents).decode("ascii")
        return {"image_b64": byte_data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))