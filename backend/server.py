from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fileSystem import FileSystem
from config import *

app = FastAPI(title="OS File System Simulator API")
fs = FileSystem()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WriteRequest(BaseModel):
    filename: str
    content: str

class TouchRequest(BaseModel):
    filename: str

@app.post("/api/format")
def api_format():
    fs.format()
    return {"message": "Disk formatted successfully."}

@app.post("/api/touch")
def api_touch(req: TouchRequest):
    try:
        ino = fs.touch(req.filename)
        return {"message": f"Created {req.filename}", "inode": ino}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/write")
def api_write(req: WriteRequest):
    try:
        fs.write(req.filename, req.content)
        return {"message": f"Written to {req.filename}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/state")
def api_state():
    # Return blocks & inodes for the visualizer grid
    inodes = [fs.read_inode(i) for i in range(TOTAL_INODES)]
    return {
        "blocks_count": TOTAL_BLOCKS,
        "block_size": BLOCK_SIZE,
        "inodes": inodes,
        "files": fs.list_dir(0)
    }
