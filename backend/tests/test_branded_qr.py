import struct
import zlib
from xml.etree import ElementTree
import pytest
from app.services.branded_qr import layout, qr_svg, qr_png


@pytest.mark.parametrize('length', [150, 650, 1050, 1200, 1500, 2000])
def test_branded_formats_keep_border_and_small_logo(length):
    value = 'happ://crypt5/' + ('aBcD0123+/=' * length)[:length]
    matrix, start, size = layout(value)
    assert not any(any(row) for row in matrix[:4])
    assert size / (len(matrix)-8) <= .14
    svg = ElementTree.fromstring(qr_svg(value))
    assert len(svg.findall('.//{http://www.w3.org/2000/svg}polyline')) == 2
    png = qr_png(value)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    width, height = struct.unpack('!II', png[16:24])
    assert width == height == len(matrix)*8
    offset, compressed = 8, b''
    while offset < len(png):
        count = struct.unpack('!I', png[offset:offset+4])[0]
        kind, data = png[offset+4:offset+8], png[offset+8:offset+8+count]
        assert struct.unpack('!I',png[offset+8+count:offset+12+count])[0] == zlib.crc32(kind+data)&0xffffffff
        if kind == b'IDAT': compressed += data
        offset += count + 12
    raw = zlib.decompress(compressed)
    assert len(raw) == height*(1+width*3)
    assert bytes((8,127,130)) in raw
