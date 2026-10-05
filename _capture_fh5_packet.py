"""Capture raw Forza telemetry packets from the game and dump key offsets.

Only accepts packets with IsRaceOn == 1 (i.e. you are actually in a race and the
game is filling in data). Packets sent from menus/pause are 324 bytes of zeros,
which look like a parse failure but are not - so they are counted and reported
separately instead of being mistaken for the real thing.

ASCII-only output on purpose: a Windows console using a legacy code page (GBK,
cp1252, ...) raises UnicodeEncodeError on non-ASCII prints, which kills the
script mid-run. Everything here is plain ASCII so it works on any console.

Usage (close Virtual TCU first - it holds the UDP port):

    python _capture_fh5_packet.py            # default port 5555
    python _capture_fh5_packet.py 5300       # custom port

Writes: _capture_fh5_packet.bin  (raw race packets)
        _capture_fh5_packet.txt  (report)
"""

import os
import socket
import struct
import sys
import time
import traceback

DEFAULT_PORT = 5555
MAX_SAMPLES = 8
DEADLINE_S = 90.0  # total time to keep looking for race packets


def main() -> int:
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"[WARN] bad port argument {sys.argv[1]!r}, using {DEFAULT_PORT}")

    print("Virtual TCU FH5 packet capture", flush=True)
    print(f"Python : {sys.version.split()[0]}  ({sys.executable})", flush=True)
    print(f"Binding UDP port {port} ...", flush=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as e:
        print(f"[ERROR] cannot bind UDP {port}: {e}", flush=True)
        print("        Is Virtual TCU still running? Close it first (Ctrl+C / tray Quit).")
        return 1

    print(f"[OK] listening on 0.0.0.0:{port}", flush=True)
    print("", flush=True)
    print(">>> BE IN A RACE AND DRIVING. Driving with a controller is fine. <<<", flush=True)
    print(f"    Waiting up to {DEADLINE_S:.0f}s for {MAX_SAMPLES} race packets ...", flush=True)
    print("", flush=True)

    sock.settimeout(0.5)
    samples: list[bytes] = []
    idle_packets = 0
    total_packets = 0
    last_notice = 0.0
    start = time.time()

    try:
        while len(samples) < MAX_SAMPLES and (time.time() - start) < DEADLINE_S:
            try:
                raw, addr = sock.recvfrom(2048)
            except socket.timeout:
                raw = None
            except OSError as e:
                print(f"[WARN] receive error: {e}", flush=True)
                break

            if raw is None:
                if idle_packets and (time.time() - last_notice) > 5.0:
                    print(
                        f"    ... still waiting: {idle_packets} packets seen but all "
                        f"report IsRaceOn=0 (menus/pause). Start driving!",
                        flush=True,
                    )
                    last_notice = time.time()
                continue

            total_packets += 1
            if len(raw) >= 4 and struct.unpack_from("<i", raw, 0)[0] == 1:
                samples.append(raw)
                print(f"  race packet {len(samples)}: {len(raw)} bytes from {addr}", flush=True)
            else:
                idle_packets += 1
                if idle_packets == 1:
                    print(
                        "  [i] got a packet with IsRaceOn=0 (menu/pause) - ignoring it. "
                        "Get on track and drive.",
                        flush=True,
                    )
                last_notice = time.time()
    finally:
        sock.close()

    if not samples:
        print("", flush=True)
        print("[ERROR] No RACE packets captured.", flush=True)
        print(f"  datagrams seen: {total_packets}  (all IsRaceOn=0: {idle_packets})", flush=True)
        print("  - Data Out is working: packets ARE arriving.", flush=True)
        print("  - But the game reports 'not racing', so the data is empty.", flush=True)
        print("  - Run this again and be ON TRACK, DRIVING, during the wait.", flush=True)
        return 1

    pkt = samples[-1]
    lines = []
    lines.append(f"samples={len(samples)} sizes={sorted({len(s) for s in samples})}")
    lines.append(f"last packet length={len(pkt)}")
    lines.append(f"datagrams seen={total_packets} (idle/menu={idle_packets})")
    lines.append("")
    lines.append("=== key offsets (last RACE packet) ===")

    fields = [
        (0, "IsRaceOn", "i32"),
        (4, "TimestampMS", "u32"),
        (8, "EngineMaxRpm", "f32"),
        (12, "EngineIdleRpm", "f32"),
        (16, "CurrentEngineRpm", "f32"),
        (20, "AccelerationX", "f32"),
        (24, "AccelerationY", "f32"),
        (28, "AccelerationZ", "f32"),
        (32, "VelocityX", "f32"),
        (36, "VelocityY", "f32"),
        (40, "VelocityZ", "f32"),
        (212, "CarOrdinal", "i32"),
        (216, "CarClass", "i32"),
        (220, "CarPerformanceIndex", "i32"),
        (224, "DrivetrainType", "i32"),
        (228, "NumCylinders", "i32"),
        (244, "PositionX", "f32"),
        (248, "PositionY", "f32"),
        (252, "PositionZ", "f32"),
        (256, "Speed", "f32"),
        (260, "Power", "f32"),
        (264, "Torque", "f32"),
        (268, "TireTempFL", "f32"),
        (284, "Boost", "f32"),
        (288, "Fuel", "f32"),
        (312, "LapNumber", "u16"),
        (314, "RacePosition", "u8"),
        (315, "Accel", "u8"),
        (316, "Brake", "u8"),
        (317, "Clutch", "u8"),
        (318, "HandBrake", "u8"),
        (319, "Gear", "u8"),
    ]

    max_rpm = 0.0
    speed = 0.0
    for off, name, kind in fields:
        if kind == "f32" and off + 4 <= len(pkt):
            v = struct.unpack_from("<f", pkt, off)[0]
            bits = struct.unpack_from("<I", pkt, off)[0]
            extra = f"  bits=0x{bits:08X}"
        elif kind in ("i32", "u32") and off + 4 <= len(pkt):
            v = struct.unpack_from("<i", pkt, off)[0]
            extra = ""
        elif kind == "u16" and off + 2 <= len(pkt):
            v = struct.unpack_from("<H", pkt, off)[0]
            extra = ""
        elif kind == "u8" and off < len(pkt):
            v = pkt[off]
            extra = ""
        else:
            v, extra = "N/A", ""
        lines.append(f"  offset {off:>3}  {name:<20} = {v}{extra}")
        if name == "EngineMaxRpm" and isinstance(v, float):
            max_rpm = v
        if name == "Speed" and isinstance(v, float):
            speed = v

    ok_rpm = 0.0 < max_rpm <= 30000.0
    ok_spd = 0.0 <= speed <= 250.0
    lines.append("")
    lines.append("=== sanity check used by this FH5 build ===")
    lines.append(f"  EngineMaxRpm={max_rpm}  requirement 0<x<=30000  -> {ok_rpm}")
    lines.append(f"  Speed={speed}  requirement 0<=x<=250  -> {ok_spd}")
    lines.append(f"  packet would be ACCEPTED: {ok_rpm and ok_spd}")

    # Which byte ranges actually carry data? Tells us at a glance whether the
    # layout we assume is the layout the game is sending.
    nonzero = [i for i, b in enumerate(pkt) if b != 0]
    lines.append("")
    lines.append(f"=== non-zero bytes: {len(nonzero)} of {len(pkt)} ===")
    if nonzero:
        lines.append(f"  first non-zero offset={nonzero[0]}  last={nonzero[-1]}")
        ranges = []
        run_start = prev = nonzero[0]
        for i in nonzero[1:]:
            if i == prev + 1:
                prev = i
                continue
            ranges.append((run_start, prev))
            run_start = prev = i
        ranges.append((run_start, prev))
        lines.append("  contiguous ranges: " + ", ".join(f"{a}-{b}" for a, b in ranges[:24]))
    else:
        lines.append("  ALL ZERO - the game sent an empty frame")

    lines.append("")
    lines.append("=== first 64 bytes hex ===")
    lines.append("  " + pkt[:64].hex(" "))
    lines.append("=== last 32 bytes hex ===")
    lines.append("  " + pkt[-32:].hex(" "))

    report = "\n".join(lines)
    print("", flush=True)
    print(report, flush=True)

    bin_path = "_capture_fh5_packet.bin"
    txt_path = "_capture_fh5_packet.txt"
    with open(bin_path, "wb") as f:
        for s in samples:
            f.write(struct.pack("<H", len(s)))
            f.write(s)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"port={port}\n" + report + "\n")

    print("", flush=True)
    print(f"[OK] wrote {bin_path} and {txt_path}", flush=True)
    print(f"     full path: {os.path.abspath(txt_path)}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    try:
        code = main()
    except Exception:
        print("[FATAL] unexpected error:")
        traceback.print_exc()
        code = 2
    try:
        input("Press Enter to exit...")
    except Exception:
        pass
    sys.exit(code)
