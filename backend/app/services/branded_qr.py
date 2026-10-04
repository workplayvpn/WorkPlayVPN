"""One QR layout for the Mini App (SVG) and Telegram (lossless PNG)."""
import struct
import zlib

import qrcode
from qrcode.exceptions import DataOverflowError

WP_LINES = (
    ((.13, .30), (.22, .70), (.31, .43), (.40, .70), (.49, .30)),
    ((.60, .70), (.60, .30), (.79, .30), (.86, .36), (.86, .46), (.79, .52), (.60, .52)),
)


def layout(value):
    for correction, fraction in ((qrcode.constants.ERROR_CORRECT_H, .09),
                                 (qrcode.constants.ERROR_CORRECT_Q, .07),
                                 (qrcode.constants.ERROR_CORRECT_M, .05)):
        code = qrcode.QRCode(error_correction=correction, border=4)
        code.add_data(value)
        try:
            code.make(fit=True)
            break
        except (DataOverflowError, ValueError):
            continue
    else:
        raise DataOverflowError('Happ key exceeds QR capacity')
    matrix = code.get_matrix()
    n = len(matrix)
    size = max(5, int((n - 8) * fraction))
    if size % 2 == 0:
        size += 1
    return matrix, (n - size) // 2, size


def qr_svg(value):
    matrix, start, size = layout(value)
    n = len(matrix)
    cells = ''.join(f'M{x} {y}h1v1h-1z' for y, row in enumerate(matrix) for x, dark in enumerate(row) if dark)
    strokes = ''.join(
        '<polyline points="' + ' '.join(f'{start+x*size:.3f},{start+y*size:.3f}' for x, y in line) + '"/>'
        for line in WP_LINES
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{n*8}" height="{n*8}">'
        f'<rect width="{n}" height="{n}" fill="white"/><path d="{cells}" fill="black"/>'
        f'<rect x="{start}" y="{start}" width="{size}" height="{size}" fill="white"/>'
        f'<g fill="none" stroke="#087f82" stroke-width="{size*.065}" stroke-linecap="round" stroke-linejoin="round">{strokes}</g></svg>'
    ).encode()


def qr_png(value):
    matrix, start, size = layout(value)
    scale = 8
    width = len(matrix) * scale
    pixels = bytearray(b'\xff' * (width * width * 3))

    def square(x, y, side, color):
        for row in range(max(0, y), min(width, y + side)):
            left, right = max(0, x), min(width, x + side)
            pixels[(row*width+left)*3:(row*width+right)*3] = bytes(color) * (right-left)

    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                square(x*scale, y*scale, scale, (0, 0, 0))
    square(start*scale, start*scale, size*scale, (255, 255, 255))
    thickness = max(2, round(size*scale*.065))
    for line in WP_LINES:
        points = [(round((start+x*size)*scale), round((start+y*size)*scale)) for x, y in line]
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            steps = max(abs(x2-x1), abs(y2-y1), 1)
            for i in range(steps+1):
                x = round(x1+(x2-x1)*i/steps)
                y = round(y1+(y2-y1)*i/steps)
                square(x-thickness//2, y-thickness//2, thickness, (8, 127, 130))

    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind+data) & 0xffffffff)

    rows = b''.join(b'\x00'+pixels[y*width*3:(y+1)*width*3] for y in range(width))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, width, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
