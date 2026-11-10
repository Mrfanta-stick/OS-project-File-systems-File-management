import struct

# Geometry & Constants
BLOCK_SIZE=512
TOTAL_BLOCKS=128
DISK_SIZE=BLOCK_SIZE*TOTAL_BLOCKS # 512 x 128 = 64KB

MAGIC_NUMBER=0x53595346 # SYSF in big endian OR FSYS in little endian

# Block locations (0-127)
SUPERBLOCK_BLOCK=0
INODE_BITMAP_BLOCK=1
DATA_BITMAP_BLOCK=2
INODE_TABLE_START_BLOCK=3
INODE_TABLE_BLOCKS=8
FIRST_DATA_BLOCK=11
TOTAL_DATA_BLOCKS=TOTAL_BLOCKS-FIRST_DATA_BLOCK # 117

TOTAL_INODES=32
INODE_SIZE=128 # bytes

# File types
TYPE_FREE=0
TYPE_FILE=1
TYPE_DIR=2

# Standard Default Permissions (Octal)
DEFAULT_DIR_PERM = 0o755   # rwxr-xr-x
DEFAULT_FILE_PERM = 0o644  # rw-r--r--

# Permission Bitmasks
PERM_READ = 0o400   # Owner read
PERM_WRITE = 0o200  # Owner write
PERM_EXEC = 0o100   # Owner execute (traversal for directories)

# Inode pointer limits
NUM_DIRECT_POINTERS=4

# Binary format: Little endian
# Superblock: magic(4B), total blocks(2B), block size(2B), total inodes(2B),
#             inode table start(2B), first data block(2B), padding(498B)
SUPERBLOCK_FORMAT="<I H H H H H"

# Inode: Perm(2B), file type(2B), size(2B), direct ptrs(4*2B = 8B), indirect Ptrs(2B), padding(112B)
INODE_FORMAT="<H H I 4H H"

# Directory Entry: inode idx(2B), filename(14B ASCII, null-padded) -> 16B per entry
DENTRY_FORMAT = "<H 14s"
DENTRY_SIZE = 16
ENTRIES_PER_BLOCK = BLOCK_SIZE // DENTRY_SIZE  # 32 entries per directory block
