from fastapi import APIRouter, Request, Response, Depends, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from fastapi_csrf_protect import CsrfProtect

from ..main import app, limiter
from ..infra.db_tagging import MongoDB
from ..infra.storage import S3
from ..infra.sessions import Redis
from ..services.computer_vision import yolov11_detect_img_objects

router = APIRouter(
    prefix="/snap",
    tags=["snap"],
    responses={ 401: { "description": "Unauthorized" } },
)

# Pydantic models
class AllSnapsResponse(BaseModel):
    img_url: str
    created_at: str
    file_size: int
    s3_key: str
    tags: list[str]
    caption: str

class KeyAndCaption(BaseModel):
    s3_key: str
    caption: str = Field(..., min_length=1, max_length=300)

# Error handling
class SnapError(Exception):
    "Exception for snap operations"
    pass
    
def _raise_snap_operation_error(func_name: str, error: Exception) -> None:
    error_message = f"Failed to perform snap operation in {func_name}: {error}"
    
    app.state.logger.log_error(error_message)
    raise SnapError(error_message) from error

@router.get("/all", response_model=list[AllSnapsResponse])
@limiter.limit("30/minute")
async def all(request: Request, csrf_protect: CsrfProtect = Depends()):
    await csrf_protect.validate_csrf(request)
    
    try:
        session_key = request.cookies.get("session_key")
        
        session = Redis.get_session(session_key)
        user_id = session["user_id"]
        
        snaps = S3.read_snaps(user_id)
        img_tags_and_captions = MongoDB.read_img_tags_and_captions(user_id)
        
        snaps_with_tags_and_captions = []
        
        for snap, tags_and_caption in zip(snaps, img_tags_and_captions):
            snaps_with_tags_and_captions.append({
                "img_url": snap["img_url"],
                "created_at": snap["created_at"],
                "file_size": snap["file_size"],
                "s3_key": snap["s3_key"],
                "tags": tags_and_caption["tags"],
                "caption": tags_and_caption["caption"],
            })
        
        return snaps_with_tags_and_captions
    
    except Exception as e:
        _raise_snap_operation_error("all", e)

@router.post("/upload")
@limiter.limit("325/minute")
async def upload(
    request: Request,
    img_file: UploadFile,
    csrf_protect: CsrfProtect = Depends(),
):
    await csrf_protect.validate_csrf(request)
    
    try:
        session_key = request.cookies.get("session_key")
        
        session = Redis.get_session(session_key)
        user_id = session["user_id"]
        
        img_url, s3_key = await S3.upload_snap(user_id, img_file)
        Redis.place_thumbnail_img_url(session_key, img_url)
        tags = await yolov11_detect_img_objects(img_file)
        MongoDB.add_img_tags(user_id, s3_key, tags)
        
        return Response(status_code=200)
        
    except Exception as e:
        _raise_snap_operation_error("upload", e)

@router.post("/caption")
@router.put("/caption")
@limiter.limit("50/minute")
async def caption(
    request: Request,
    key_and_caption: KeyAndCaption,
    csrf_protect: CsrfProtect = Depends(),
):
    await csrf_protect.validate_csrf(request)
    
    try:
        s3_key = key_and_caption.s3_key
        caption = key_and_caption.caption
        
        MongoDB.write_img_caption(s3_key, caption)
        
        return Response(status_code=200)
        
    except Exception as e:
        _raise_snap_operation_error("caption", e)
    
@router.delete("/single")
async def delete_single(
    request: Request,
    s3_key: str,
    csrf_protect: CsrfProtect = Depends(),
):
    await csrf_protect.validate_csrf(request)
    
    try:
        S3.delete_snap(s3_key)
        MongoDB.delete_img_tags_and_captions(s3_key)
        
        return Response(status_code=200)
    
    except Exception as e:
        _raise_snap_operation_error("delete_single", e)
