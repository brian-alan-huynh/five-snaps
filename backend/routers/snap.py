from fastapi import APIRouter, Request, Response, UploadFile
from fastapi.responses import RedirectResponse

from ..infra.db_tagging import MongoDB
from ..infra.storage import S3
from ..infra.sessions import Redis
from ..services.computer_vision import yolov11_detect_img_objects

router = APIRouter(
    prefix="/snap",
    tags=["snap"],
    responses={ 401: { "description": "Unauthorized" } },
)

@router.get("/all")
async def all(request: Request):
    try:
        session_key = request.cookies.get("session_key")
        session = Redis.get_session(session_key)
        
        if not session:
            return RedirectResponse(url="http://localhost:3000/error?where=all&reason=session+fetch+error", status_code=401)
        
        user_id = session["user_id"]
        
        snaps = S3.read_snaps(user_id)
        
        if not snaps:
            return RedirectResponse(url="http://localhost:3000/error?where=all&reason=snaps+read+error", status_code=400)
        
        img_tags_and_captions = MongoDB.read_img_tags_and_captions(user_id)
        
        if not img_tags_and_captions:
            return RedirectResponse(url="http://localhost:3000/error?where=all&reason=img+tags+and+captions+read+error", status_code=400)
        
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
        return RedirectResponse(url=f"http://localhost:3000/error?where=all&reason={e}", status_code=500)

@router.post("/upload")
async def upload(request: Request, img_file: UploadFile):
    try:
        session_key = request.cookies.get("session_key")
        session = Redis.get_session(session_key)
        
        if not session:
            return RedirectResponse(url="http://localhost:3000/error?where=upload&reason=session+fetch+error", status_code=401)
        
        user_id = session["user_id"]
        
        res_upload = await S3.upload_snap(user_id, img_file)
        
        if not res_upload:
            return RedirectResponse(url="http://localhost:3000/error?where=upload&reason=snap+upload+error", status_code=400)
        
        img_url, s3_key = res_upload
        
        res_thumbnail = Redis.place_thumbnail_img_url(session_key, img_url)
        
        if not res_thumbnail:
            return RedirectResponse(url="http://localhost:3000/error?where=upload&reason=thumbnail+upload+error", status_code=400)
        
        tags = await yolov11_detect_img_objects(img_file)
        
        if not tags:
            return RedirectResponse(url="http://localhost:3000/error?where=upload&reason=computer+vision+error", status_code=400)
        
        res_add_img_tags = MongoDB.add_img_tags(user_id, s3_key, tags)
        
        if not res_add_img_tags:
            return RedirectResponse(url="http://localhost:3000/error?where=upload&reason=img+tags+add+error", status_code=400)
        
        return Response(status_code=200)
        
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=upload&reason={e}", status_code=500)

@router.post("/caption")
@router.put("/caption")
async def caption(s3_key: str, caption: str):
    try:
        res_write_img_caption = MongoDB.write_img_caption(s3_key, caption)
        
        if not res_write_img_caption:
            return RedirectResponse(url="http://localhost:3000/error?where=caption&reason=img+caption+write+error", status_code=400)
        
        return Response(status_code=200)
        
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=caption&reason={e}", status_code=500)
    
@router.delete("/single")
async def delete_single(s3_key: str):
    try:
        res_delete_snap = S3.delete_snap(s3_key)
        
        if not res_delete_snap:
            return RedirectResponse(url="http://localhost:3000/error?where=delete_single&reason=snap+delete+error", status_code=400)
        
        res_delete_img_tags_and_captions = MongoDB.delete_img_tags_and_captions(s3_key)
        
        if not res_delete_img_tags_and_captions:
            return RedirectResponse(url="http://localhost:3000/error?where=delete_single&reason=img+tags+and+captions+delete+error", status_code=400)
        
        return Response(status_code=200)
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=delete_single&reason={e}", status_code=500)
