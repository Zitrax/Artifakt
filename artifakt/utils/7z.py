import struct

from collections import defaultdict


def rint(f):
    """Reads one byte as unsigned integer (0-255)"""
    return struct.unpack("<B", f.read(1))[0]


def uint64(f):
    """Read an UINT64

    This format is described in 7zFormat.txt in 7z.
    Implementation based on 7zln.cpp.
    """
    b = rint(f)
    mask = 0x80
    value = 0
    for i in range(8):
        if b & mask == 0:
            high_part = b & (mask - 1)
            value += (high_part << (i * 8))
            return value
        value |= (rint(f) << (8 * i))
        mask >>= 1
    return value


def dir7z(filename):
    with open(filename, mode='rb+') as f:
        if f.read(6) != b"7z\xbc\xaf'\x1c":
            raise ValueError("Not a 7z signature")
        major, minor = f.read(2)
        print("VER: {}.{}".format(major, minor))
        # 7z use little endian, so '<'
        crc = struct.unpack("<I", f.read(4))[0]
        print("CRC: {}".format(crc))
        next_header_offset = struct.unpack("<Q", f.read(8))[0]
        next_header_size = struct.unpack("<Q", f.read(8))[0]
        next_header_crc = struct.unpack("<I", f.read(4))[0]
        print("NHO: {}".format(next_header_offset))
        print("NHS: {}".format(next_header_size))
        print("NHC: {}".format(next_header_crc))
        # Move to next header
        f.read(next_header_offset)
        id = f.read(1)
        if id == b'\x17':  # Header Info
            # Read Streams Info
            id = f.read(1)
            while id != b'\x00':
                if id == b'\x06':  # Pack info
                    pack_pos = uint64(f)
                    num_pack_streams = uint64(f)
                    iid = f.read(1)
                    while iid != b'\x00':
                        if iid == b'\x09':  # kSize
                            for _ in range(num_pack_streams):
                                uint64(f)
                        if iid == b'\x0A':  # kCRC
                            f.read(4 * num_pack_streams)
                        iid = f.read(1)
                if id == b'\x07':  # CodersInfo
                    assert f.read(1) == b'\x0B'  # kFolder
                    num_folders = uint64(f)
                    out_streams_per_folder = defaultdict(int)
                    if rint(f) == 0:  # Folders
                        num_coders = uint64(f)
                        num_out_streams_total = None
                        num_in_streams_total = None
                        for i in range(num_coders):
                            bits = rint(f)
                            codec_id_size = bits & 0xF
                            is_complex_coder = bool(bits & 0x10)
                            there_are_attributes = bool(bits & 0x20)
                            f.read(codec_id_size)
                            if is_complex_coder:
                                num_in_streams_total += uint64(f)
                                out_streams_per_folder[i] = uint64(f)
                                num_out_streams_total += out_streams_per_folder[i]
                            else:
                                num_out_streams_total = 1
                                num_in_streams_total = 1
                                out_streams_per_folder[i] = 1
                            if there_are_attributes:
                                properties_size = uint64(f)
                                f.read(properties_size)
                        num_bind_pairs = num_out_streams_total - 1
                        for _ in range(num_bind_pairs):
                            uint64(f)  # InIndex
                            uint64(f)  # OutIndex
                        num_packed_streams = num_in_streams_total - num_bind_pairs
                        if num_packed_streams > 1:
                            for _ in range(num_packed_streams):
                                uint64(f)
                    else:
                        uint64(f)  # DataStreamIndex
                    assert f.read(1) == b'\x0C'  # kCodersUnPackSize
                    for i in range(num_folders):
                        for _ in range(out_streams_per_folder[i]):
                            uint64(f)  # UnPackSize
                    id_crc = f.read(1)
                    if id_crc == b'\x0A':  # kCRC
                        if f.read(1) == b'\x00':
                            for _ in num_folders:
                                raise NotImplemented("ReadBoolVector")
                        f.read(4 * num_folders)
                        id_crc = f.read(1)
                    assert id_crc == b'\x00'

                id = f.read(1)

                #  SubStreamsInfo
                #  NID::kEnd


# Want FilesInfo, which is in "Header"

if __name__ == '__main__':
    print(dir7z('C:/Users/Daniel/Documents/test.7z'))
