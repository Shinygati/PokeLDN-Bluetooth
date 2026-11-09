"""3DS UDS cryptography: the beacon node data (AES-CTR) and the CCMP data key.

Neither key ships with pokeldn. Both are the user's own console's:

- the NWM beacon key, a constant inside the NWM system module, and
- the normal key of AES keyslot 0x2D, which NWM uses to derive each network's CCMP key from the
  application's passphrase ([3dbrew NWM_Services], Azahar's ``GenerateDataCCMPKey``).

``load_keys`` reads them from a text file of ``name=hex`` lines (Azahar's aes_keys.txt works for
the slot key: ``slot0x2DKeyN``).
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from Crypto.Cipher import AES

from .frames import NetworkInfo


@dataclass
class UdsKeys:
    beacon: bytes | None = None       # NWM beacon key
    data: bytes | None = None         # keyslot 0x2D normal key


def load_keys(path: str | Path) -> UdsKeys:
    keys = UdsKeys()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        name, value = name.strip().lower(), value.strip().replace(" ", "")
        if not value or name.startswith("#"):
            continue
        if name in ("nwm_beacon_key", "uds_beacon_key", "beacon"):
            keys.beacon = _key(value, name)
        elif name in ("slot0x2dkeyn", "uds_data_key", "data"):
            keys.data = _key(value, name)
    return keys


def _key(text: str, name: str) -> bytes:
    key = bytes.fromhex(text)
    if len(key) != 16:
        raise ValueError(f"{name} must be 16 bytes")
    return key


# -------------------------------------------------------------------------------------------------
# Beacon node data

def beacon_counter(host_mac: bytes, info: NetworkInfo) -> bytes:
    """BeaconDataCryptoCTR: host MAC, u32 LE wlan comm id, u8 id, pad, u32 LE network id."""
    return bytes(host_mac) + struct.pack("<IBxI", info.wlan_comm_id, info.id, info.network_id)


def crypt_beacon_data(key: bytes, host_mac: bytes, info: NetworkInfo, data: bytes) -> bytes:
    """AES-CTR in both directions (encrypting and decrypting are the same)."""
    counter = beacon_counter(host_mac, info)
    cipher = AES.new(key, AES.MODE_CTR, nonce=b"", initial_value=counter)
    return cipher.encrypt(data)


# -------------------------------------------------------------------------------------------------
# CCMP

def data_counter(host_mac: bytes, info: NetworkInfo) -> bytes:
    """MD5 of DataFrameCryptoCTR: u32 LE wlan comm id, u32 LE network id, host MAC, u16 LE id."""
    plain = struct.pack("<II", info.wlan_comm_id, info.network_id) + bytes(host_mac) + struct.pack("<H", info.id)
    return hashlib.md5(plain).digest()


def ccmp_key(slot_key: bytes, passphrase: bytes, host_mac: bytes, info: NetworkInfo) -> bytes:
    """The network's CCMP key: AES-CTR(slot 0x2D, counter) over MD5(passphrase)."""
    cipher = AES.new(slot_key, AES.MODE_CTR, nonce=b"", initial_value=data_counter(host_mac, info))
    return cipher.encrypt(hashlib.md5(passphrase).digest())


def _aad(header: bytes) -> bytes:
    """IEEE 802.11 CCMP AAD from a three-address data frame header (24 bytes)."""
    fc, = struct.unpack_from("<H", header)
    # Subtype bits 4-6, retry, power management and more data masked; protected set. (Azahar writes
    # this mask as 0x8FC7 because it holds the field big-endian.)
    fc = (fc & 0xC78F) | 0x4000
    seq_ctl, = struct.unpack_from("<H", header, 22)
    return struct.pack("<H", fc) + header[4:22] + struct.pack("<H", seq_ctl & 0x000F)


def _nonce(header: bytes, pn: int) -> bytes:
    return b"\0" + header[10:16] + pn.to_bytes(6, "big")


def ccmp_header(pn: int, key_id: int = 0) -> bytes:
    p = pn.to_bytes(6, "little")
    return bytes([p[0], p[1], 0, 0x20 | (key_id << 6), p[2], p[3], p[4], p[5]])


def ccmp_encrypt(key: bytes, header: bytes, pn: int, body: bytes, key_id: int = 0) -> bytes:
    """A protected frame from a 24-byte header (protected bit set here) and a plaintext body."""
    header = bytearray(header[:24])
    header[1] |= 0x40
    cipher = AES.new(key, AES.MODE_CCM, nonce=_nonce(header, pn), mac_len=8)
    cipher.update(_aad(bytes(header)))
    sealed, tag = cipher.encrypt_and_digest(body)
    return bytes(header) + ccmp_header(pn, key_id) + sealed + tag


def ccmp_decrypt(key: bytes, frame: bytes) -> tuple[int, bytes]:
    """(packet number, plaintext body) of a protected three-address data frame; raises on a bad MIC."""
    header, ccmp, rest = frame[:24], frame[24:32], frame[32:]
    if not ccmp[3] & 0x20:
        raise ValueError("no CCMP extended IV")
    pn = int.from_bytes(bytes([ccmp[0], ccmp[1], ccmp[4], ccmp[5], ccmp[6], ccmp[7]]), "little")
    cipher = AES.new(key, AES.MODE_CCM, nonce=_nonce(header, pn), mac_len=8)
    cipher.update(_aad(header))
    return pn, cipher.decrypt_and_verify(rest[:-8], rest[-8:])
