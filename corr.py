import os
import random


def corrupt_docx(input_path, output_path, corruption_ratio=0.01):
    """
    Membuat file .docx menjadi corrupt dengan mengubah sebagian byte.

    :param input_path: Path file .docx asli
    :param output_path: Path file .docx hasil corrupt
    :param corruption_ratio: Persentase byte yang akan dirusak (default 1%)
    """
    with open(input_path, "rb") as f:
        data = bytearray(f.read())

    num_bytes_to_corrupt = int(len(data) * corruption_ratio)

    for _ in range(num_bytes_to_corrupt):
        index = random.randint(0, len(data) - 1)
        data[index] = random.randint(0, 255)

    with open(output_path, "wb") as f:
        f.write(data)

    print(f"File corrupt berhasil dibuat: {output_path}")


# Contoh penggunaan
corrupt_docx(
    "/Users/admin/Desktop/ppl/excel-generator-mono/test.docx",
    "/Users/admin/Desktop/ppl/excel-generator-mono/corr.docx",
)
