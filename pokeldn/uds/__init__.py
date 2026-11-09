"""Nintendo 3DS local wireless (UDS) for the Gen 6 and Gen 7 Mystery Gift work.

The structures follow Azahar's nwm::UDS and the retail captures in Gr3nSkyDragon's azahar_uds fork:

- ``frames``: beacon bodies and their Nintendo tags, LLC/SNAP, the SecureData header, EAPoL-Start and
  EAPoL-Logoff, and authentication and association response bodies.
- ``bridge``: the plaintext UDP datagrams azahar_uds exchanges with another program
  (``AZAHAR_UDS_BRIDGE``), and a relay between two emulator instances that records every packet.
- ``crypto``: the beacon tag AES-CTR and the CCMP data-key derivation. Both keys come from the
  user's own console, never from this repository.

docs/3ds_uds.md describes the plan and how to record a Local Distributor session.
"""
