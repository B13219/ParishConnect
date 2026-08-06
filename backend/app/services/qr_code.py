from html import escape

VERSION = 10
SIZE = VERSION * 4 + 17
DATA_CODEWORDS = 274
ECC_CODEWORDS = 18
BLOCK_COUNT = 4
ALIGNMENT_POSITIONS = (6, 28, 50)


def make_qr_svg(data: str, scale: int = 7, border: int = 4) -> str:
    modules, reserved = blank_matrix()
    draw_function_patterns(modules, reserved)
    codewords = encode_codewords(data)
    draw_codewords(modules, reserved, codewords)
    apply_mask(modules, reserved)
    draw_format_bits(modules, reserved)
    draw_version_bits(modules, reserved)
    return render_svg(modules, scale, border)


def blank_matrix() -> tuple[list[list[bool]], list[list[bool]]]:
    return (
        [[False for _ in range(SIZE)] for _ in range(SIZE)],
        [[False for _ in range(SIZE)] for _ in range(SIZE)],
    )


def set_module(
    modules: list[list[bool]],
    reserved: list[list[bool]],
    x: int,
    y: int,
    dark: bool,
    *,
    reserve: bool = True,
) -> None:
    if 0 <= x < SIZE and 0 <= y < SIZE:
        modules[y][x] = dark
        if reserve:
            reserved[y][x] = True


def draw_function_patterns(modules: list[list[bool]], reserved: list[list[bool]]) -> None:
    draw_finder(modules, reserved, 0, 0)
    draw_finder(modules, reserved, SIZE - 7, 0)
    draw_finder(modules, reserved, 0, SIZE - 7)

    for i in range(8, SIZE - 8):
        dark = i % 2 == 0
        set_module(modules, reserved, i, 6, dark)
        set_module(modules, reserved, 6, i, dark)

    for x in ALIGNMENT_POSITIONS:
        for y in ALIGNMENT_POSITIONS:
            if (x, y) in {(6, 6), (6, SIZE - 7), (SIZE - 7, 6)}:
                continue
            draw_alignment(modules, reserved, x, y)

    set_module(modules, reserved, 8, SIZE - 8, True)


def draw_finder(
    modules: list[list[bool]],
    reserved: list[list[bool]],
    left: int,
    top: int,
) -> None:
    for y in range(-1, 8):
        for x in range(-1, 8):
            xx = left + x
            yy = top + y
            dark = 0 <= x <= 6 and 0 <= y <= 6 and (x in {0, 6} or y in {0, 6} or 2 <= x <= 4 and 2 <= y <= 4)
            set_module(modules, reserved, xx, yy, dark)


def draw_alignment(
    modules: list[list[bool]],
    reserved: list[list[bool]],
    center_x: int,
    center_y: int,
) -> None:
    for y in range(-2, 3):
        for x in range(-2, 3):
            dark = max(abs(x), abs(y)) != 1
            set_module(modules, reserved, center_x + x, center_y + y, dark)


def encode_codewords(data: str) -> list[int]:
    payload = data.encode("utf-8")
    if len(payload) > 255:
        raise ValueError("QR payload is too long for the configured symbol.")

    bits: list[int] = []
    append_bits(bits, 0b0100, 4)
    append_bits(bits, len(payload), 16)
    for byte in payload:
        append_bits(bits, byte, 8)

    remaining_bits = DATA_CODEWORDS * 8 - len(bits)
    append_bits(bits, 0, min(4, remaining_bits))
    while len(bits) % 8:
        bits.append(0)

    data_codewords = [
        int("".join(str(bit) for bit in bits[i : i + 8]), 2)
        for i in range(0, len(bits), 8)
    ]
    pad = 0xEC
    while len(data_codewords) < DATA_CODEWORDS:
        data_codewords.append(pad)
        pad ^= 0xEC ^ 0x11

    blocks = split_blocks(data_codewords)
    ecc_blocks = [reed_solomon_remainder(block, ECC_CODEWORDS) for block in blocks]
    result: list[int] = []
    max_data_len = max(len(block) for block in blocks)
    for i in range(max_data_len):
        for block in blocks:
            if i < len(block):
                result.append(block[i])
    for i in range(ECC_CODEWORDS):
        for block in ecc_blocks:
            result.append(block[i])
    return result


def append_bits(bits: list[int], value: int, length: int) -> None:
    for i in range(length - 1, -1, -1):
        bits.append((value >> i) & 1)


def split_blocks(data_codewords: list[int]) -> list[list[int]]:
    return [
        data_codewords[0:68],
        data_codewords[68:136],
        data_codewords[136:205],
        data_codewords[205:274],
    ]


def reed_solomon_remainder(data: list[int], degree: int) -> list[int]:
    generator = reed_solomon_generator(degree)
    result = [0] * degree
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coefficient in enumerate(generator):
            result[i] ^= gf_multiply(coefficient, factor)
    return result


def reed_solomon_generator(degree: int) -> list[int]:
    result = [1]
    for i in range(degree):
        result.append(0)
        root = gf_pow(2, i)
        for j in range(len(result) - 1):
            result[j] = gf_multiply(result[j], root) ^ result[j + 1]
    return result[:-1]


def gf_pow(value: int, power: int) -> int:
    result = 1
    for _ in range(power):
        result = gf_multiply(result, value)
    return result


def gf_multiply(x: int, y: int) -> int:
    result = 0
    while y:
        if y & 1:
            result ^= x
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
        y >>= 1
    return result


def draw_codewords(
    modules: list[list[bool]],
    reserved: list[list[bool]],
    codewords: list[int],
) -> None:
    bits = [(byte >> i) & 1 == 1 for byte in codewords for i in range(7, -1, -1)]
    bit_index = 0
    upward = True
    x = SIZE - 1
    while x > 0:
        if x == 6:
            x -= 1
        for i in range(SIZE):
            y = SIZE - 1 - i if upward else i
            for dx in (0, 1):
                xx = x - dx
                if not reserved[y][xx] and bit_index < len(bits):
                    modules[y][xx] = bits[bit_index]
                    bit_index += 1
        upward = not upward
        x -= 2


def apply_mask(modules: list[list[bool]], reserved: list[list[bool]]) -> None:
    for y in range(SIZE):
        for x in range(SIZE):
            if not reserved[y][x] and (x + y) % 2 == 0:
                modules[y][x] = not modules[y][x]


def draw_format_bits(modules: list[list[bool]], reserved: list[list[bool]]) -> None:
    bits = format_bits(error_correction_level=1, mask=0)
    for i in range(15):
        dark = ((bits >> i) & 1) == 1
        if i < 6:
            set_module(modules, reserved, 8, i, dark)
        elif i < 8:
            set_module(modules, reserved, 8, i + 1, dark)
        else:
            set_module(modules, reserved, 8, SIZE - 15 + i, dark)

        if i < 8:
            set_module(modules, reserved, SIZE - 1 - i, 8, dark)
        elif i < 9:
            set_module(modules, reserved, 15 - i, 8, dark)
        else:
            set_module(modules, reserved, 14 - i, 8, dark)


def format_bits(error_correction_level: int, mask: int) -> int:
    data = (error_correction_level << 3) | mask
    value = data << 10
    for i in range(14, 9, -1):
        if (value >> i) & 1:
            value ^= 0x537 << (i - 10)
    return ((data << 10) | value) ^ 0x5412


def draw_version_bits(modules: list[list[bool]], reserved: list[list[bool]]) -> None:
    bits = version_bits(VERSION)
    for i in range(18):
        dark = ((bits >> i) & 1) == 1
        x = SIZE - 11 + i % 3
        y = i // 3
        set_module(modules, reserved, x, y, dark)
        set_module(modules, reserved, y, x, dark)


def version_bits(version: int) -> int:
    value = version << 12
    for i in range(17, 11, -1):
        if (value >> i) & 1:
            value ^= 0x1F25 << (i - 12)
    return (version << 12) | value


def render_svg(modules: list[list[bool]], scale: int, border: int) -> str:
    size = (SIZE + border * 2) * scale
    rects = []
    for y, row in enumerate(modules):
        for x, dark in enumerate(row):
            if dark:
                rects.append(
                    f'<rect x="{(x + border) * scale}" y="{(y + border) * scale}" '
                    f'width="{scale}" height="{scale}"/>'
                )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" role="img" aria-label="{escape(data_label())}">'
        f'<rect width="100%" height="100%" fill="#fff"/>'
        f'<g fill="#000">{"".join(rects)}</g></svg>'
    )


def data_label() -> str:
    return "ParishConnect attendance QR code"
