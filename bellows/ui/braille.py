"""Drawing primitives shared by terminal waveform and loop renderers."""

BRAILLE_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))


def draw_line(
    canvas: list[list[bool]],
    start: tuple[int, int],
    end: tuple[int, int],
) -> None:
    x1, y1 = start
    x2, y2 = end
    steps = max(abs(x2 - x1), abs(y2 - y1), 1)

    for step in range(steps + 1):
        fraction = step / steps
        x = round(x1 + (x2 - x1) * fraction)
        y = round(y1 + (y2 - y1) * fraction)
        canvas[y][x] = True


def cell_mask(canvas: list[list[bool]], char_x: int, char_y: int) -> int:
    mask = 0
    for sub_y, bits in enumerate(BRAILLE_BITS):
        for sub_x, bit in enumerate(bits):
            if canvas[char_y * 4 + sub_y][char_x * 2 + sub_x]:
                mask |= bit
    return mask
