import os
import struct
from config import (
    BLOCK_SIZE, DISK_SIZE, DATA_BITMAP_BLOCK, FIRST_DATA_BLOCK, TOTAL_DATA_BLOCKS
)

class RawDisk:
    def __init__(self, disk_path="virtual_disk.bin"):
        self.disk_path = disk_path

    def init_empty_disk(self):
        with open(self.disk_path, "wb") as f:
            f.write(bytearray(DISK_SIZE))

    def read_block(self, block_num: int) -> bytearray:
        with open(self.disk_path, "rb") as f:
            f.seek(block_num * BLOCK_SIZE)
            return bytearray(f.read(BLOCK_SIZE))

    def write_block(self, block_num: int, data: bytes):
        padded_data = bytearray(data) + bytearray(BLOCK_SIZE - len(data))
        with open(self.disk_path, "r+b") as f:
            f.seek(block_num * BLOCK_SIZE)
            f.write(padded_data)

    # Bitwise Operations (Bit Vector Management)
    @staticmethod
    def get_bit(bitmap: bytearray, bit_idx: int) -> int:
        return (bitmap[bit_idx // 8] >> (bit_idx % 8)) & 1

    @staticmethod
    def set_bit(bitmap: bytearray, bit_idx: int, val: int):
        if val:
            bitmap[bit_idx // 8] |= (1 << (bit_idx % 8))
        else:
            bitmap[bit_idx // 8] &= ~(1 << (bit_idx % 8))

    @staticmethod
    def find_free_bit(bitmap: bytearray, max_bits: int):
        for i in range(max_bits):
            if RawDisk.get_bit(bitmap, i) == 0: # First-Fit
                return i
        return None

    def allocate_data_block(self) -> int:
        bitmap = self.read_block(DATA_BITMAP_BLOCK)
        free_bit = self.find_free_bit(bitmap, TOTAL_DATA_BLOCKS)
        if free_bit is None:
            raise RuntimeError("Disk full: no free data blocks.")
        
        self.set_bit(bitmap, free_bit, 1)
        self.write_block(DATA_BITMAP_BLOCK, bitmap)
        
        phys_block = FIRST_DATA_BLOCK + free_bit
        self.write_block(phys_block, bytearray(BLOCK_SIZE))  # Zero out new block
        return phys_block

    def free_data_block(self, phys_block: int):
        bitmap = self.read_block(DATA_BITMAP_BLOCK)
        free_bit = phys_block - FIRST_DATA_BLOCK
        self.set_bit(bitmap, free_bit, 0)
        self.write_block(DATA_BITMAP_BLOCK, bitmap)
