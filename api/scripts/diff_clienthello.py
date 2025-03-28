import sys

def read_file(path):
    with open(path, "rb") as f:
        return f.read()

def hex_ascii_line(byte_line):
    hex_part = " ".join(f"{b:02x}" for b in byte_line)
    ascii_part = "".join(chr(b) if 32 <= b <= 126 else '.' for b in byte_line)
    return f"{hex_part:<48}  {ascii_part}"

def compare_bytes(b1, b2):
    print("Offset | Python Payload                         | Librespot Payload                      | Match")
    print("-" * 90)
    for i in range(0, max(len(b1), len(b2)), 16):
        py_chunk = b1[i:i+16]
        lib_chunk = b2[i:i+16]
        match = py_chunk == lib_chunk
        print(
            f"{i:06x} | {hex_ascii_line(py_chunk)} | {hex_ascii_line(lib_chunk)} | {'✅' if match else '❌'}"
        )
        if not match:
            # Optional: Stop early at first mismatch
            print(f"\n🔍 Mismatch at byte offset {i}")
            break

def main():
    py = read_file("clienthello_py.raw")
    lib = read_file("clienthello.raw")

    if py == lib:
        print("✅ Files match exactly!")
    else:
        print("❗ Files differ!")
        compare_bytes(py, lib)

if __name__ == "__main__":
    main()
