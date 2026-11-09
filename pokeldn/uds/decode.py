"""Readable summaries of recorded UDS packets (the relay's capture lines)."""

from __future__ import annotations

from .frames import (Beacon, EapolLogoff, EapolStart, EtherType, EAPOL_LOGOFF, EAPOL_START,
                     parse_association_response, split_llc, unpack_secure_data)

TYPES = ("beacon", "data", "authentication", "association_response", "deauthentication", "node_map")


def describe(record: dict) -> list[str]:
    """One or more lines describing a capture record (data packets get one line per SecureData)."""
    data = bytes.fromhex(record["data"])
    kind = record["type"]
    head = f"{record['from']} {record['src']} -> {record['dst']} ch{record['channel']} {kind}"
    try:
        if kind == "beacon":
            return [head + " " + describe_beacon(data)]
        if kind == "authentication":
            alg, seq, status = (int.from_bytes(data[i:i + 2], "little") for i in (0, 2, 4))
            return [head + f" alg={alg} seq={seq} status={status}"]
        if kind == "association_response":
            caps, status, aid = parse_association_response(data)
            return [head + f" caps={caps:#06x} status={status} aid={aid} ssid={data[8:16].decode('ascii', 'replace')}"]
        if kind == "data":
            return describe_data(head, data)
    except (ValueError, IndexError) as error:
        return [head + f" undecoded ({error}) {data.hex()}"]
    return [head + f" {len(data)} bytes {data.hex()}"]


def describe_beacon(data: bytes) -> str:
    beacon = Beacon.parse(data)
    info = beacon.network_info
    if not info:
        return f"(no Nintendo network info) {len(data)} bytes"
    return (f"comm_id={info.wlan_comm_id:#010x} id={info.id:#04x} attributes={info.attributes:#06x} "
            f"network_id={info.network_id:#010x} nodes={info.total_nodes}/{info.max_nodes} "
            f"sha1={'ok' if info.sha1_ok else 'BAD'} appdata[{len(info.application_data)}]={info.application_data.hex()}")


def describe_data(head: str, data: bytes) -> list[str]:
    ethertype, body = split_llc(data)
    if ethertype == EtherType.EAPOL:
        magic = int.from_bytes(body[:2], "big")
        if magic == EAPOL_START:
            start = EapolStart.unpack(body)
            return [head + f" EAPoL-Start aid={start.association_id} conn={start.connection_type} "
                           f"user={start.node.username!r} fc_seed={start.node.friend_code_seed:#018x}"]
        if magic == EAPOL_LOGOFF:
            logoff = EapolLogoff.unpack(body)
            nodes = ", ".join(f"{n.network_node_id}:{n.username!r}" for n in logoff.nodes)
            return [head + f" EAPoL-Logoff node={logoff.assigned_node_id} status={logoff.host_status} "
                           f"{logoff.connected_nodes}/{logoff.max_nodes} [{nodes}]"]
        return [head + f" EAPoL magic={magic:#06x} {body.hex()}"]
    if ethertype == EtherType.SECURE_DATA:
        return [head + f" SD{' mgmt' if p.is_management else ''} ch={p.channel} seq={p.sequence} "
                       f"{p.src_node}->{p.dest_node:#x} [{len(p.payload)}] {p.payload.hex()}"
                for p in unpack_secure_data(body)]
    return [head + f" ethertype={ethertype:#06x} {body.hex()}"]
