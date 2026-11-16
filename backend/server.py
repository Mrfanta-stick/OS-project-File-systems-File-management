import os
import sys

# Ensure Backend/ is in sys.path even if uvicorn is launched from Project/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
DISK_PATH = os.path.join(BASE_DIR, "virtual_disk.bin")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from fileSystem import FileSystem
from disk import RawDisk
from config import *

app = FastAPI(title="OS File System Simulator")
fs = FileSystem(DISK_PATH)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auto-format virtual disk on first boot if missing
if not os.path.exists(DISK_PATH):
    fs.format()

# REQUEST SCHEMAS
class PathRequest(BaseModel):
    path: str

class WriteRequest(BaseModel):
    path: str
    content: str

class ChmodRequest(BaseModel):
    path: str
    mode: str  # Accepts "0400", "400", or "0o400"

# FILE SYSTEM ENDPOINTS
@app.post("/api/format")
def api_format():
    fs.format()
    return {"message": "Disk formatted (64 KB, 128 blocks, 32 inodes)."}

@app.post("/api/mkdir")
def api_mkdir(req: PathRequest):
    try:
        ino = fs.mkdir(req.path)
        return {"message": f"Created directory '{req.path}' (Inode {ino}).", "inode": ino}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/touch")
def api_touch(req: PathRequest):
    try:
        ino = fs.touch(req.path)
        return {"message": f"Created file '{req.path}' (Inode {ino}).", "inode": ino}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/write")
def api_write(req: WriteRequest):
    try:
        fs.write(req.path, req.content)
        return {"message": f"Written {len(req.content)} bytes to '{req.path}'."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/cat")
def api_cat(path: str):
    try:
        content = fs.cat(path)
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chmod")
def api_chmod(req: ChmodRequest):
    try:
        octal_mode = int(req.mode, 8)
        fs.chmod(req.path, octal_mode)
        return {"message": f"Permissions for '{req.path}' set to {oct(octal_mode)}."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/rm")
def api_rm(req: PathRequest):
    try:
        fs.rm(req.path)
        return {"message": f"Deleted '{req.path}' and reclaimed blocks."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/rmdir")
def api_rmdir(req: PathRequest):
    try:
        fs.rmdir(req.path)
        return {"message": f"Removed empty directory '{req.path}'."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# FULL DISK & METADATA SNAPSHOT FOR VISUALIZER
@app.get("/api/state")
def api_state():
    inode_bmp = fs.disk.read_block(INODE_BITMAP_BLOCK)
    data_bmp = fs.disk.read_block(DATA_BITMAP_BLOCK)

    inodes = []
    inode_bits = []
    for i in range(TOTAL_INODES):
        bit = RawDisk.get_bit(inode_bmp, i)
        inode_bits.append(bit)
        ino = fs.read_inode(i)
        ino["allocated"] = bool(bit)
        inodes.append(ino)

    data_bits = [RawDisk.get_bit(data_bmp, i) for i in range(TOTAL_DATA_BLOCKS)]
    blocks = []
    for b in range(TOTAL_BLOCKS):
        category = "free"
        owner = None

        if b == SUPERBLOCK_BLOCK:
            category = "superblock"
        elif b == INODE_BITMAP_BLOCK:
            category = "inode_bitmap"
        elif b == DATA_BITMAP_BLOCK:
            category = "data_bitmap"
        elif INODE_TABLE_START_BLOCK <= b < (INODE_TABLE_START_BLOCK + INODE_TABLE_BLOCKS):
            category = "inode_table"
        else:
            bit_idx = b - FIRST_DATA_BLOCK
            if RawDisk.get_bit(data_bmp, bit_idx) == 1:
                category = "data"
                for ino in inodes:
                    if ino["allocated"]:
                        if b in ino["direct"]:
                            owner = ino["index"]
                            if ino["type"] == TYPE_DIR:
                                category = "dir_data"
                        elif b == ino["indirect"]:
                            category = "indirect_index"
                            owner = ino["index"]

        blocks.append({"id": b, "category": category, "owner": owner})

    return {
        "blocks": blocks,
        "inodes": inodes,
        "inode_bitmap": inode_bits,
        "data_bitmap": data_bits,
        "tree_ascii": fs.tree(),
        "tree_json": fs.get_tree_json()
    }

# SERVE FRONTEND
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_ui():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
