# Unix-like Inode File System & Block Allocator

An interactive Operating Systems project that implements a Unix-style Inode file system over a raw binary virtual disk (`virtual_disk.bin`), paired with a FastAPI backend and a browser-based visualization dashboard.

---

## 1. Theoretical Background

This implementation models the core on-disk and in-memory structures of a hierarchical file system (based on Silberschatz, Galvin, and Gagne, Chapters 10 and 11):

* **On-Disk File-System Structure:** Physical storage is divided into fixed-size logical blocks (512 bytes each). Specific regions are reserved for volume metadata (Superblock), free-space bitmaps, File Control Blocks (Inodes), and raw file data.
* **File Control Blocks (Inodes):** Every file or directory is represented by a fixed-size Inode containing its type, access permissions, byte size, and block pointers. Inodes do not store filenames; filenames are decoupled and stored inside directory entries.
* **Indexed Allocation (Direct and Single Indirect Pointers):** To prevent external fragmentation while supporting variable file sizes, each Inode maintains 4 direct block pointers (covering up to 4 x 512 = 2048 bytes) and 1 single indirect pointer. When a file exceeds 2KB, an additional Index Block is dynamically allocated to store 2-byte addresses for up to 256 extra data blocks.
* **Free-Space Management (Bit Vectors):** Free and allocated states for both Inodes and Data Blocks are tracked using bitmaps (`0` = free, `1` = allocated). Bitwise operations (`&`, `|`, `~`) locate the first available slot (First-Fit allocation) and reclaim space upon deletion.
* **Directory Implementation and Path Resolution:** Directories are special files whose data blocks contain a linear list of fixed-size directory entries (`16 bytes` each: a `2-byte` Inode number and a `14-byte` ASCII name). Every directory initializes with self (`.`) and parent (`..`) links to support hierarchical path resolution.
* **File Protection:** Access control is enforced using POSIX-style octal permission bits (`rwx` for owner, group, and others) stored inside each Inode. Read (`cat`) and write (`write`) system calls validate these permission masks before accessing data blocks.

---

## 2. Virtual Disk Geometry

The virtual storage file (`virtual_disk.bin`) has a total capacity of 64 KB, partitioned into 128 blocks of 512 bytes each:

| Block Range | Region | Description |
| :--- | :--- | :--- |
| Block 0 | Superblock | Stores magic number (`0x53595346`), total block count, block size, total Inode count, and region offsets. |
| Block 1 | Inode Bitmap | Bit vector tracking allocation status for 32 Inodes. |
| Block 2 | Data Block Bitmap | Bit vector tracking allocation status for 117 usable data blocks. |
| Blocks 3 to 10 | Inode Table | 8 blocks (4096 bytes total) holding 32 Inodes at 128 bytes per Inode. |
| Blocks 11 to 127 | Data Blocks | 117 blocks used for file payloads, directory entries, and indirect index blocks. |

### Binary Struct Layouts (Little-Endian)

* **Superblock (`<I H H H H H`):** Magic number (`4B`), total blocks (`2B`), block size (`2B`), total Inodes (`2B`), Inode table start (`2B`), first data block (`2B`).
* **Inode (`<H H I 4H H`):** File type (`2B`), permission mode (`2B`), size in bytes (`4B`), 4 direct pointers (`8B`), 1 indirect pointer (`2B`).
* **Directory Entry (`<H 14s`):** Target Inode index (`2B`), null-padded filename (`14B`).

---

## 3. Project Structure

```text
OS PROJECT - FILE SYSTEM/
├── backend/
│   ├── config.py           # Disk geometry constants, bitmasks, and binary struct formats
│   ├── disk.py             # Raw block I/O device driver and bitwise bitmap operations
│   ├── fileSystem.py       # Inode management, directory traversal, permissions, and FS commands
│   ├── server.py           # FastAPI REST endpoints and static frontend host
│   └── virtual_disk.bin    # Raw 64 KB binary disk image (auto-generated on startup)
├── frontend/
│   └── index.html          # Interactive shell, 128-block grid visualizer, bitmaps, and Inode table
└── README.md
│
└── requirements.txt
```

---

## 4. Setup and Execution

### Prerequisites

* Python 3.8 or higher
* `fastapi` and `uvicorn`

### Installation and Running

1. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Navigate to the `backend` directory and launch the server:
   ```bash
   cd backend
   uvicorn server:app --reload
   ```

3. Open a web browser and navigate to:
   ```text
   http://localhost:8000
   ```

### Raw Binary Inspection (Optional)

Because `virtual_disk.bin` stores real packed binary structures, you can inspect the on-disk bytes directly from your terminal using `xxd` or `hexdump`:

```bash
# View the Superblock header at Block 0
xxd -l 32 backend/virtual_disk.bin

# View the Inode Table starting at Block 3 (byte offset 1536)
xxd -s 1536 -l 256 backend/virtual_disk.bin
```

---

## 5. Supported Shell Commands

The web dashboard includes an interactive shell supporting the following operations:

* `mkfs` — Formats `virtual_disk.bin`, resets bitmaps, and initializes the root directory `/` at Inode 0.
* `mkdir <path>` — Creates a new directory with `.` and `..` links (e.g., `mkdir /docs`).
* `touch <path>` — Allocates a new Inode with default `0644` permissions and links it into the parent directory.
* `write <path> <text>` — Writes text content to a file, allocating direct blocks and an indirect index block if the payload exceeds 2048 bytes.
* `cat <path>` — Reads and displays file contents by traversing direct and indirect pointers (requires read permission).
* `chmod <octal> <path>` — Updates permission bits on a file or directory (e.g., `chmod 0400 /docs/notes.txt`).
* `rm <path>` — Deletes a file, frees its direct and indirect data blocks in the bitmap, and clears its Inode.
* `rmdir <path>` — Deletes an empty directory and reclaims its Inode and data block.