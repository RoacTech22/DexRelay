import struct

from app.memory.pointers import (
    SLOT_DATA_SIZE,
    BLOCK_SIZE,
)


def crypt(data, seed, i):
    value = data[i]
    value ^= (seed >> 16) & 0xFF

    result = struct.pack(
        "B",
        value
    )

    value = data[i + 1]
    value ^= (seed >> 24) & 0xFF

    result += struct.pack(
        "B",
        value
    )

    return result


def crypt_array(data, seed, start, end):
    result = bytes()
    temp_seed = seed

    for i in range(start, end, 2):
        temp_seed *= 0x41C64E6D
        temp_seed &= 0xFFFFFFFF

        temp_seed += 0x6073
        temp_seed &= 0xFFFFFFFF

        result += crypt(
            data,
            temp_seed,
            i
        )

    return result


def shuffle_array(data, sv, block_size):
    block_position = [
        [
            0, 0, 0, 0, 0, 0,
            1, 1, 2, 3, 2, 3,
            1, 1, 2, 3, 2, 3,
            1, 1, 2, 3, 2, 3
        ],

        [
            1, 1, 2, 3, 2, 3,
            0, 0, 0, 0, 0, 0,
            2, 3, 1, 1, 3, 2,
            2, 3, 1, 1, 3, 2
        ],

        [
            2, 3, 1, 1, 3, 2,
            2, 3, 1, 1, 3, 2,
            0, 0, 0, 0, 0, 0,
            3, 2, 3, 2, 1, 1
        ],

        [
            3, 2, 3, 2, 1, 1,
            3, 2, 3, 2, 1, 1,
            3, 2, 3, 2, 1, 1,
            0, 0, 0, 0, 0, 0
        ]
    ]

    result = bytes()

    for block in range(4):
        start = (
            block_size
            * block_position[block][sv]
        )

        end = start + block_size

        result += data[start:end]

    return result


def decrypt_data(encrypted_data):
    if not encrypted_data:
        return b""

    if len(encrypted_data) < SLOT_DATA_SIZE:
        return b""

    try:
        pv = struct.unpack(
            "<I",
            encrypted_data[:4]
        )[0]

        sv = (
            (pv >> 0xD)
            & 0x1F
        ) % 24

        start = 8

        end = (
            4 * BLOCK_SIZE
        ) + start

        header = encrypted_data[:8]

        blocks = crypt_array(
            encrypted_data,
            pv,
            start,
            end
        )

        # Checksum incorporado del formato PK6: la
        # cabecera (bytes 0x06-0x07, sin cifrar) guarda
        # la suma de 16 bits de los 4 bloques recién
        # descifrados, EN SU ORDEN FISICO original (antes
        # de reordenarlos con shuffle_array).
        #
        # Si la memoria se leyo a mitad de una escritura
        # del juego (por ejemplo justo cuando evoluciona
        # o se reordena la party), el descifrado igual
        # "funciona" pero produce basura: species_id
        # aleatorio (evoluciones fantasma) y nickname
        # aleatorio (que al decodificarse como texto cae
        # a menudo en caracteres CJK). El checksum es
        # justo lo que el formato ofrece para detectar
        # esto, asi que se descarta la lectura si no
        # coincide, en vez de confiar ciegamente en un
        # descifrado que "parece" valido.
        stored_checksum = struct.unpack(
            "<H",
            encrypted_data[6:8]
        )[0]

        calculated_checksum = sum(
            struct.unpack(
                f"<{len(blocks) // 2}H",
                blocks
            )
        ) & 0xFFFF

        if calculated_checksum != stored_checksum:
            return b""

        stats = crypt_array(
            encrypted_data,
            pv,
            end,
            len(encrypted_data)
        )

        shuffled = shuffle_array(
            blocks,
            sv,
            BLOCK_SIZE
        )

        return (
            header
            + shuffled
            + stats
        )

    except Exception:
        return b""


class Pokemon6:
    def __init__(self, encrypted_data):
        self.raw_data = b""

        if not encrypted_data:
            return

        if len(encrypted_data) < SLOT_DATA_SIZE:
            return

        # Comprobación de estructura vacía.
        if all(
            byte == 0
            for byte in encrypted_data[:8]
        ):
            return

        decrypted = decrypt_data(
            encrypted_data
        )

        if decrypted:
            self.raw_data = decrypted

    def species_id(self):
        if len(self.raw_data) < 0x0A:
            return 0

        return struct.unpack(
            "<H",
            self.raw_data[0x08:0x0A]
        )[0]

    def nickname(self):
        if len(self.raw_data) < 0x58:
            return ""

        raw_name = self.raw_data[
            0x40:0x58
        ]

        try:
            name = raw_name.decode(
                "utf-16le",
                errors="ignore"
            )

            name = name.split(
                "\x00",
                1
            )[0]

            return name

        except Exception:
            return ""

    def level(self):
        if len(self.raw_data) <= 0xEC:
            return 0

        return self.raw_data[0xEC]

    def hp(self):
        if len(self.raw_data) < 0xF2:
            return 0

        return struct.unpack(
            "<H",
            self.raw_data[0xF0:0xF2]
        )[0]

    def max_hp(self):
        if len(self.raw_data) < 0xF4:
            return 0

        return struct.unpack(
            "<H",
            self.raw_data[0xF2:0xF4]
        )[0]