import struct
import math
from config import *
from disk import RawDisk

class FileSystem:
    def __init__(self, disk_path="virtual_disk.bin"):
        self.disk = RawDisk(disk_path)

    def format(self):
        self.disk.init_empty_disk()
        
        # 1. Superblock
        sb = struct.pack(SUPERBLOCK_FORMAT, MAGIC_NUMBER, TOTAL_BLOCKS, BLOCK_SIZE, 
                         TOTAL_INODES, INODE_TABLE_START_BLOCK, FIRST_DATA_BLOCK)
        self.disk.write_block(SUPERBLOCK_BLOCK, sb)

        # 2. Inode & Data Bitmaps
        inode_bmp = bytearray(BLOCK_SIZE)
        data_bmp = bytearray(BLOCK_SIZE)
        RawDisk.set_bit(inode_bmp, 0, 1)  # Inode 0 (Root)
        RawDisk.set_bit(data_bmp, 0, 1)   # Block 11 (Root dir entries)
        self.disk.write_block(INODE_BITMAP_BLOCK, inode_bmp)
        self.disk.write_block(DATA_BITMAP_BLOCK, data_bmp)

        # 3. Root Inode
        root_inode = struct.pack(INODE_FORMAT, TYPE_DIR, DENTRY_SIZE * 2, FIRST_DATA_BLOCK, 0, 0, 0, 0)
        self.write_inode(0, root_inode)

        # 4. Root Directory Data Block ('.' and '..')
        dblock = bytearray(BLOCK_SIZE)
        struct.pack_into(DENTRY_FORMAT, dblock, 0, 0, b".")
        struct.pack_into(DENTRY_FORMAT, dblock, DENTRY_SIZE, 0, b"..")
        self.disk.write_block(FIRST_DATA_BLOCK, dblock)

    def read_inode(self, idx: int):
        offset = (INODE_TABLE_START_BLOCK * BLOCK_SIZE) + (idx * INODE_SIZE)
        with open(self.disk.disk_path, "rb") as f:
            f.seek(offset)
            raw = f.read(struct.calcsize(INODE_FORMAT))
        f_type, size, d0, d1, d2, d3, indirect = struct.unpack(INODE_FORMAT, raw)
        return {"index": idx, "type": f_type, "size": size, "direct": [d0, d1, d2, d3], "indirect": indirect}

    def write_inode(self, idx: int, raw_bytes: bytes):
        offset = (INODE_TABLE_START_BLOCK * BLOCK_SIZE) + (idx * INODE_SIZE)
        with open(self.disk.disk_path, "r+b") as f:
            f.seek(offset)
            f.write(raw_bytes)

    def list_dir(self, dir_inode_idx=0):
        inode = self.read_inode(dir_inode_idx)
        entries = []
        for blk in inode["direct"]:
            if blk == 0: continue
            data = self.disk.read_block(blk)
            for i in range(ENTRIES_PER_BLOCK):
                ino, name_bytes = struct.unpack(DENTRY_FORMAT, data[i*DENTRY_SIZE : (i+1)*DENTRY_SIZE])
                name = name_bytes.decode("ascii", errors="ignore").rstrip("\x00")
                if name:
                    entries.append({"inode": ino, "name": name})
        return entries

    def touch(self, filename: str):
        inode_bmp = self.disk.read_block(INODE_BITMAP_BLOCK)
        free_ino = RawDisk.find_free_bit(inode_bmp, TOTAL_INODES)
        if free_ino is None: raise RuntimeError("Out of Inodes.")

        # Mark Inode allocated
        RawDisk.set_bit(inode_bmp, free_ino, 1)
        self.disk.write_block(INODE_BITMAP_BLOCK, inode_bmp)

        # Write blank Inode
        empty_ino = struct.pack(INODE_FORMAT, TYPE_FILE, 0, 0, 0, 0, 0, 0)
        self.write_inode(free_ino, empty_ino)

        # Add to root directory
        dblock = self.disk.read_block(FIRST_DATA_BLOCK)
        for i in range(ENTRIES_PER_BLOCK):
            _, raw_n = struct.unpack(DENTRY_FORMAT, dblock[i*DENTRY_SIZE : (i+1)*DENTRY_SIZE])
            if raw_n.decode("ascii", errors="ignore").rstrip("\x00") == "":
                struct.pack_into(DENTRY_FORMAT, dblock, i*DENTRY_SIZE, free_ino, filename.encode("ascii")[:14])
                self.disk.write_block(FIRST_DATA_BLOCK, dblock)
                return free_ino
        raise RuntimeError("Root directory is full.")

    def write(self, filename: str, content: str):
        entries = self.list_dir(0)
        target = next((e for e in entries if e["name"] == filename), None)
        if not target: raise FileNotFoundError(f"File {filename} not found.")

        payload = content.encode("utf-8")
        needed = math.ceil(len(payload) / BLOCK_SIZE)
        allocated = [self.disk.allocate_data_block() for _ in range(needed)]

        for i, blk in enumerate(allocated):
            self.disk.write_block(blk, payload[i*BLOCK_SIZE : (i+1)*BLOCK_SIZE])

        directs = [allocated[i] if i < len(allocated) else 0 for i in range(4)]
        indirect = 0
        if needed > 4:
            indirect = self.disk.allocate_data_block()
            idx_data = bytearray(BLOCK_SIZE)
            for i, blk in enumerate(allocated[4:]):
                struct.pack_into("<H", idx_data, i*2, blk)
            self.disk.write_block(indirect, idx_data)

        packed = struct.pack(INODE_FORMAT, TYPE_FILE, len(payload), *directs, indirect)
        self.write_inode(target["inode"], packed)
