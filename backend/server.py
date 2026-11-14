import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fileSystem import FileSystem
from config import *

app = FastAPI(title="OS File System Simulator API")
fs = FileSystem()
if not os.path.exists(fs.disk.disk_path):
    fs.format()

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
    # Read information about all inodes from the inode table
    inodes = [fs.read_inode(i) for i in range(TOTAL_INODES)]

    # Read the data block bitmap
    # Each bit represents whether a data block is free or allocated
    bitmap = fs.disk.read_block(DATA_BITMAP_BLOCK)

    # Store the physical block numbers of all allocated data blocks
    allocated_blocks = [
        FIRST_DATA_BLOCK + i
        for i in range(TOTAL_DATA_BLOCKS)
        if (bitmap[i // 8] >> (i % 8)) & 1
    ]

    # Return disk information in JSON format for the React frontend
    return {
        "blocks_count": TOTAL_BLOCKS,
        "block_size": BLOCK_SIZE,
        "inodes": inodes,
        "files": fs.list_dir(0),

        # Send allocated block numbers to the Disk Visualizer
        "allocated_blocks": allocated_blocks
    }
