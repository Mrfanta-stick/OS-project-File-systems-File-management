import struct
import math
from config import *
from disk import RawDisk

class FileSystem:
    def __init__(self, disk_path="virtual_disk.bin"):
        self.disk = RawDisk(disk_path)

    @staticmethod
    def mode_to_str(mode: int, file_type: int) -> str:
        # Converts an octal mode into standard 'rwxr-xr-x' format
        prefix = "d" if file_type == TYPE_DIR else "-"
        perms = [
            ("r", 0o400), ("w", 0o200), ("x", 0o100),
            ("r", 0o040), ("w", 0o020), ("x", 0o010),
            ("r", 0o004), ("w", 0o002), ("x", 0o001),
        ]
        return prefix + "".join(c if mode & mask else "-" for c, mask in perms)

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

        # 3. Root Inode (Type=DIR, Mode=0o755, Size=32 bytes, Direct=[11,0,0,0], Indirect=0)
        root_inode = struct.pack(INODE_FORMAT, TYPE_DIR, DEFAULT_DIR_PERM, DENTRY_SIZE * 2, FIRST_DATA_BLOCK, 0, 0, 0, 0)
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
        f_type, mode, size, d0, d1, d2, d3, indirect = struct.unpack(INODE_FORMAT, raw)
        return {
            "index": idx, 
            "type": f_type,
            "mode": mode,
            "permissions": self.mode_to_str(mode, f_type),
            "size": size, 
            "direct": [d0, d1, d2, d3], 
            "indirect": indirect
        }

    def write_inode(self, idx: int, raw_bytes: bytes):
        offset = (INODE_TABLE_START_BLOCK * BLOCK_SIZE) + (idx * INODE_SIZE)
        with open(self.disk.disk_path, "r+b") as f:
            f.seek(offset)
            f.write(raw_bytes)

    def list_dir(self, dir_inode_idx=0):
        inode = self.read_inode(dir_inode_idx)

        if inode["type"] != TYPE_DIR:
            raise ValueError(f"Inode {dir_inode_idx} is not a directory.")

        entries = []
        for blk in inode["direct"]:
            if blk == 0: continue
            data = self.disk.read_block(blk)
            for i in range(ENTRIES_PER_BLOCK):
                ino, name_bytes = struct.unpack(DENTRY_FORMAT, data[i*DENTRY_SIZE : (i+1)*DENTRY_SIZE])
                name = name_bytes.decode("ascii", errors="ignore").rstrip("\x00")
                if name:
                    target_inode = self.read_inode(ino)
                    entries.append({
                        "inode": ino, 
                        "name": name,
                        "type": "dir" if target_inode["type"] == TYPE_DIR else "file",
                        "size": target_inode["size"],
                        "permissions": target_inode["permissions"]
                    })
        return entries

    def _add_entry_to_dir(self, parent_inode_idx: int, name: str, child_inode_idx: int):
        # Finds an empty slot in the directory's blocks and writes (inode, name).
        parent_inode = self.read_inode(parent_inode_idx)
        name_bytes = name.encode("ascii")[:14]

        # Scan existing direct data blocks for an empty slot
        for blk in parent_inode["direct"]:
            if blk == 0: continue
            data = self.disk.read_block(blk)
            for i in range(ENTRIES_PER_BLOCK):
                _, raw_n = struct.unpack(DENTRY_FORMAT, data[i*DENTRY_SIZE : (i+1)*DENTRY_SIZE])
                if raw_n.decode("ascii", errors="ignore").rstrip("\x00") == "":
                    # Empty slot found
                    struct.pack_into(DENTRY_FORMAT, data, i*DENTRY_SIZE, child_inode_idx, name_bytes)
                    self.disk.write_block(blk, data)
                    
                    # Update parent directory size
                    new_size = parent_inode["size"] + DENTRY_SIZE
                    packed = struct.pack(
                        INODE_FORMAT, parent_inode["type"], parent_inode["mode"],
                        new_size, *parent_inode["direct"], parent_inode["indirect"]
                    )
                    self.write_inode(parent_inode_idx, packed)
                    return True

        raise RuntimeError(f"Directory {parent_inode_idx} is full.")

    def _remove_entry_from_dir(self, parent_inode_idx: int, name: str):
        parent_inode = self.read_inode(parent_inode_idx)
        for blk in parent_inode["direct"]:
            if blk == 0: continue
            data = self.disk.read_block(blk)
            for i in range(ENTRIES_PER_BLOCK):
                _, raw_n = struct.unpack(DENTRY_FORMAT, data[i*DENTRY_SIZE : (i+1)*DENTRY_SIZE])
                entry_name = raw_n.decode("ascii", errors="ignore").rstrip("\x00")
                if entry_name == name:
                    # Clear entry
                    data[i*DENTRY_SIZE : (i+1)*DENTRY_SIZE] = bytearray(DENTRY_SIZE)
                    self.disk.write_block(blk, data)
                    new_size = max(0, parent_inode["size"] - DENTRY_SIZE)
                    packed = struct.pack(
                        INODE_FORMAT, parent_inode["type"], parent_inode["mode"],
                        new_size, *parent_inode["direct"], parent_inode["indirect"]
                    )
                    self.write_inode(parent_inode_idx, packed)
                    return True
        return False

    def resolve_path(self, path: str) -> int:
        # Translates a path like '/docs/code' into its target Inode number.
        parts = [p for p in path.strip("/").split("/") if p]
        curr_inode = 0  # Root Inode

        for part in parts:
            entries = self.list_dir(curr_inode)
            matched = next((e for e in entries if e["name"] == part), None)
            if not matched:
                raise FileNotFoundError(f"Path segment '{part}' in '{path}' not found.")
            curr_inode = matched["inode"]

        return curr_inode

    def _split_parent_and_name(self, path: str):
        # Splits '/a/b/c' into (parent_inode_idx, 'c').
        parts = [p for p in path.strip("/").split("/") if p]
        if not parts:
            raise ValueError("Invalid target path.")
        if len(parts) == 1:
            return 0, parts[0]  # Direct child of root
        
        parent_path = "/" + "/".join(parts[:-1])
        target_name = parts[-1]
        parent_inode = self.resolve_path(parent_path)
        return parent_inode, target_name
    
    def mkdir(self, path: str):
        # Creates a new directory with '.' and '..' linked.
        parent_inode, dir_name = self._split_parent_and_name(path)

        # Allocate Inode
        inode_bmp = self.disk.read_block(INODE_BITMAP_BLOCK)
        free_ino = RawDisk.find_free_bit(inode_bmp, TOTAL_INODES)

        if free_ino is None: 
            raise RuntimeError("Out of Inodes.")

        RawDisk.set_bit(inode_bmp, free_ino, 1)
        self.disk.write_block(INODE_BITMAP_BLOCK, inode_bmp)

        # Allocate Data Block for the new directory
        new_data_blk = self.disk.allocate_data_block()

        # Populate with '.' (self) and '..' (parent)
        dblock = bytearray(BLOCK_SIZE)
        struct.pack_into(DENTRY_FORMAT, dblock, 0, free_ino, b".")
        struct.pack_into(DENTRY_FORMAT, dblock, DENTRY_SIZE, parent_inode, b"..")
        self.disk.write_block(new_data_blk, dblock)

        # Write new Inode
        new_inode_bytes = struct.pack(
            INODE_FORMAT, TYPE_DIR, DEFAULT_DIR_PERM, DENTRY_SIZE * 2,
            new_data_blk, 0, 0, 0, 0
        )
        self.write_inode(free_ino, new_inode_bytes)

        # Link into parent directory
        self._add_entry_to_dir(parent_inode, dir_name, free_ino)
        return free_ino

    def touch(self, path: str):
        parent_inode, filename = self. _split_parent_and_name(path)

        inode_bmp = self.disk.read_block(INODE_BITMAP_BLOCK)
        free_ino = RawDisk.find_free_bit(inode_bmp, TOTAL_INODES)
        if free_ino is None: raise RuntimeError("Out of Inodes.")

        # Mark Inode allocated
        RawDisk.set_bit(inode_bmp, free_ino, 1)
        self.disk.write_block(INODE_BITMAP_BLOCK, inode_bmp)

        # Write blank Inode
        empty_ino = struct.pack(INODE_FORMAT, TYPE_FILE, DEFAULT_FILE_PERM, 0, 0, 0, 0, 0, 0)
        self.write_inode(free_ino, empty_ino)

        # Link to parent dir
        self._add_entry_to_dir(parent_inode, filename, free_ino)
        return free_ino

    def chmod(self, path: str, new_mode: int):
        # Changes permission mode bits of a file or directory.
        target_inode_idx = self.resolve_path(path)

        inode = self.read_inode(target_inode_idx)
        # Repack Inode preserving size, pointers, and type, updating mode
        packed = struct.pack(
            INODE_FORMAT, 
            inode["type"], 
            new_mode, 
            inode["size"], 
            *inode["direct"], 
            inode["indirect"]
        )
        self.write_inode(target_inode_idx, packed)
        return True

    def write(self, path: str, content: str):
        target_inode_idx = self.resolve_path(path)
        target_inode = self.read_inode(target_inode_idx)

        if target_inode["type"] == TYPE_DIR:
            raise IsADirectoryError(f"'{path}' is a directory.")
        if not (target_inode["mode"] & PERM_WRITE):
            raise PermissionError(f"Permission denied: Write access not permitted on '{path}'.")

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

        packed = struct.pack(INODE_FORMAT, TYPE_FILE, target_inode["mode"], len(payload), *directs, indirect)
        self.write_inode(target_inode_idx, packed)

    def cat(self, path: str) -> str:
        target_inode_idx = self.resolve_path(path)
        target_inode = self.read_inode(target_inode_idx)


        # Permission check: Read only if 0o400
        if target_inode["type"] == TYPE_DIR:
            raise IsADirectoryError(f"'{path}' is a directory.")
        if not (target_inode["mode"] & PERM_READ):
            raise PermissionError(f"Permission denied: Read access not permitted on '{filename}'.")

        blocks_to_read = [blk for blk in target_inode["direct"] if blk != 0]

        if target_inode["indirect"] != 0:
            idx_data = self.disk.read_block(target_inode["indirect"])
            for i in range(BLOCK_SIZE // 2):
                (blk,) = struct.unpack_from("<H", idx_data, i * 2)
                if blk != 0:
                    blocks_to_read.append(blk)

        full_data = bytearray()
        for blk in blocks_to_read:
            full_data.extend(self.disk.read_block(blk))

        return full_data[: target_inode["size"]].decode("utf-8", errors="replace")

    def rm(self, path: str):
        # Deletes a file -> frees all direct/indirect blocks -> clears its Inode bit.
        parent_inode, filename = self._split_parent_and_name(path)
        target_inode_idx = self.resolve_path(path)
        inode = self.read_inode(target_inode_idx)

        if inode["type"] == TYPE_DIR:
            raise IsADirectoryError(f"'{path}' is a directory. Use rmdir instead.")

        # Free Direct Data Blocks in Data Bitmap
        for blk in inode["direct"]:
            if blk != 0:
                self.disk.free_data_block(blk)

        # Free Indirect Index Block and Referenced Blocks
        if inode["indirect"] != 0:
            idx_data = self.disk.read_block(inode["indirect"])
            for i in range(BLOCK_SIZE // 2):
                (blk,) = struct.unpack_from("<H", idx_data, i * 2)
                if blk != 0:
                    self.disk.free_data_block(blk)
            # Free the index block itself
            self.disk.free_data_block(inode["indirect"])

        # Free the Inode in Inode Bitmap (Block 1)
        inode_bmp = self.disk.read_block(INODE_BITMAP_BLOCK)
        RawDisk.set_bit(inode_bmp, target_inode_idx, 0)
        self.disk.write_block(INODE_BITMAP_BLOCK, inode_bmp)

        # Zero out Inode Table entry
        self.write_inode(target_inode_idx, bytearray(INODE_SIZE))

        # Remove directory entry from parent
        self._remove_entry_from_dir(parent_inode, filename)
        return True

    def rmdir(self, path: str):
        # Deletes an empty directory only, there should be no child directories or files

        # Don't delete root dir
        if path.strip("/") == "":
            raise PermissionError("Cannot delete root directory '/'.")

        parent_inode, dirname = self._split_parent_and_name(path)
        target_inode_idx = self.resolve_path(path)
        inode = self.read_inode(target_inode_idx)

        if inode["type"] != TYPE_DIR:
            raise NotADirectoryError(f"'{path}' is not a directory.")

        # Check if directory is empty (only '.' and '..' allowed)
        entries = self.list_dir(target_inode_idx)
        child_count = len([e for e in entries if e["name"] not in (".", "..")])
        if child_count > 0:
            raise RuntimeError(f"Directory '{path}' is not empty ({child_count} children exist).")

        # Free directory's data block
        for blk in inode["direct"]:
            if blk != 0:
                self.disk.free_data_block(blk)

        # Free Inode in Inode Bitmap
        inode_bmp = self.disk.read_block(INODE_BITMAP_BLOCK)
        RawDisk.set_bit(inode_bmp, target_inode_idx, 0)
        self.disk.write_block(INODE_BITMAP_BLOCK, inode_bmp)

        # Zero out Inode Table entry
        self.write_inode(target_inode_idx, bytearray(INODE_SIZE))

        # Remove from parent directory
        self._remove_entry_from_dir(parent_inode, dirname)
        return True

    def get_tree_json(self, current_inode_idx=0, name="/"):
        # Recursively constructs a nested JSON tree for frontend visualization.
        current_inode = self.read_inode(current_inode_idx)
        
        node = {
            "name": name,
            "inode": current_inode_idx,
            "type": "dir" if current_inode["type"] == TYPE_DIR else "file",
            "size": current_inode["size"],
            "permissions": current_inode["permissions"],
            "direct_blocks": [b for b in current_inode["direct"] if b != 0],
            "indirect_block": current_inode["indirect"],
            "children": []
        }

        if current_inode["type"] == TYPE_DIR:
            raw_entries = self.list_dir(current_inode_idx)
            # Filter out '.' and '..' to avoid recursive loops
            valid_entries = [e for e in raw_entries if e["name"] not in (".", "..")]
            
            for entry in valid_entries:
                child_node = self.get_tree_json(entry["inode"], entry["name"])
                node["children"].append(child_node)

        return node

    def tree(self, current_inode_idx=0, prefix="") -> str:
        # Generates standard Linux-style ASCII visual directory tree for CLI/viva.
        lines = []
        if current_inode_idx == 0 and not prefix:
            root_info = self.read_inode(0)
            lines.append(f"/ [{root_info['permissions']}] (Inode 0)")

        raw_entries = self.list_dir(current_inode_idx)
        valid_entries = [e for e in raw_entries if e["name"] not in (".", "..")]

        count = len(valid_entries)
        for i, entry in enumerate(valid_entries):
            is_last = (i == count - 1)
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            target_inode = self.read_inode(entry["inode"])
            if target_inode["type"] == TYPE_DIR:
                lines.append(f"{prefix}{connector}{entry['name']}/ [{target_inode['permissions']}] (Inode {entry['inode']})")
                subtree = self.tree(entry["inode"], prefix + extension)
                if subtree:
                    lines.append(subtree)
            else:
                lines.append(
                    f"{prefix}{connector}{entry['name']} [{target_inode['permissions']}] "
                    f"({target_inode['size']} bytes, Inode {entry['inode']})"
                )

        return "\n".join(lines)
