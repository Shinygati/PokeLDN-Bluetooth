"""Differential test: actual Android Java encoders -> actual C firmware parser and frames."""
import ctypes
import os
from pathlib import Path
import struct
import zlib
import pytest
from test_esp32_beacon3ds import Image


class Upload(ctypes.Structure):
    _fields_=[('generation',ctypes.c_uint8),('language',ctypes.c_uint8),('received',ctypes.c_uint16),
              ('fragments',(ctypes.c_uint8*112)*10)]


@pytest.fixture(scope='module')
def ds():
    root=Path(os.environ.get('POKELDN_DS_FIXTURES',''))
    if not (root/'ds_compat.dll').is_file():
        pytest.skip('Build native DS parser and Java encoder fixtures first')
    lib=ctypes.CDLL(str((root/'ds_compat.dll').resolve()))
    lib.ds_receive.argtypes=[ctypes.POINTER(Upload),ctypes.c_uint,ctypes.c_char_p,ctypes.c_size_t]
    lib.ds_image.argtypes=[ctypes.POINTER(Upload),ctypes.c_void_p,ctypes.c_size_t]
    lib.ds_image.restype=ctypes.c_size_t
    lib.advert_parse.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.POINTER(Image)]
    lib.advert_beacon_frame.argtypes=[ctypes.POINTER(Image),ctypes.c_uint,ctypes.c_uint64,ctypes.c_uint16,ctypes.c_void_p]
    lib.advert_beacon_frame.restype=ctypes.c_size_t
    return lib,root


@pytest.mark.parametrize('generation,count,interval',[(4,10,10),(5,9,21)])
def test_android_fragments_parse_and_broadcast_in_existing_radio(ds,generation,count,interval):
    lib,root=ds;state=Upload();output=ctypes.create_string_buffer(2048)
    def send(which,p):return lib.ds_receive(ctypes.byref(state),which,p,len(p))
    assert send(2,bytes([3,generation,0]))==1
    assert send(2,b'\x01')==-1  # Incomplete uploads must never start.
    data=(root/f'gen{generation}-fragments.bin').read_bytes()
    assert len(data)==count*112
    for slot in range(count):
        packet=bytes([slot])+data[slot*112:(slot+1)*112]
        assert send(1,packet)==0
    assert send(2,b'\x01')==2
    n=lib.ds_image(ctypes.byref(state),output,len(output))
    image_bytes=output.raw[:n]
    assert n==128+count*166+4
    assert zlib.crc32(image_bytes[:-4])==struct.unpack_from('<I',image_bytes,n-4)[0]
    image=Image()
    assert lib.advert_parse(image_bytes,n,ctypes.byref(image))==0
    assert image.count==count and image.channel==7 and image.interval_ms==interval
    for slot in range(count):
        frame=ctypes.create_string_buffer(2048)
        size=lib.advert_beacon_frame(ctypes.byref(image),slot,12345,slot,frame)
        assert size==188
        body=frame.raw[:size]
        assert body[10:16]==body[16:22]==bytes.fromhex('020000000001')
        assert body[76:188]==data[slot*112:(slot+1)*112]
        assert body[50:56]==bytes.fromhex('dd880009bf00')
        assert int.from_bytes(body[64:68],'little')==(0x00400318 if generation==4 else 0x1380)
    assert send(2,b'\x00')==1
    assert send(2,b'\x02')==1
    assert state.received==0 and lib.ds_image(ctypes.byref(state),output,len(output))==0


def test_invalid_control_fragment_and_crc_are_rejected(ds):
    lib,root=ds;state=Upload()
    def send(which,p):return lib.ds_receive(ctypes.byref(state),which,p,len(p))
    assert send(2,bytes([3,5,7]))==-1
    assert send(2,bytes([3,5,0]))==1
    data=bytearray((root/'gen5-fragments.bin').read_bytes()[:112]);data[24]^=1
    assert send(1,b'\0'+bytes(data))==-1
    assert send(1,b'\0')==-1
    assert send(1,b'\x09'+bytes(112))==-1
    assert send(2,b'\x01')==-1


def test_ds_then_3ds_are_at_bottom(monkeypatch):
    from pokeldn import plugins
    from pokeldn.plugins import Game
    monkeypatch.setattr(plugins,'load',lambda:None)
    monkeypatch.setattr(plugins,'_loaded',{})
    games=tuple(Game(key,key,key,'',()) for key in ('nintendo-3ds','sv','nintendo-ds','swsh'))
    monkeypatch.setattr(plugins,'_builtin_games',lambda:games)
    assert [g.key for g in plugins.games()]==['sv','swsh','nintendo-ds','nintendo-3ds']
