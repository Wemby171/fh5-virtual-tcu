"""Forza Horizon UDP telemetry parser.

Forza Horizon 5 and Forza Horizon 6 both emit the same fixed **324-byte Car
Dash** packet, so a single set of offsets covers either game. (Verified field by
field against the Horizon packet format: every offset below lands on the same
name and type in both titles.)

The real trap is the *other* Forza layouts. Motorsport's 311-byte Sled packet and
the 331-byte Motorsport Dash packet share the head of this struct but drop the
Horizon-only block, so every field from ``Speed`` onward sits 12 bytes earlier.
Feeding one of those in would "parse" into plausible-looking garbage, so they are
rejected here — and the rejection is described by :func:`describe_rejected_packet`
so the UI can tell the user what to change instead of showing a silent offline.
"""

import struct

from virtual_tcu.telemetry.model import (
    CAR_DASH_PACKET_SIZE,
    KNOWN_FOREIGN_PACKET_SIZES,
    Telemetry,
)

# Sanity bounds for a Car Dash packet. Used to confirm that an unknown-length
# packet really is Car Dash before trusting the offsets.
#
# Bounds are deliberately wide: they are here to reject a *garbage* 324-byte
# payload, not to second-guess odd-but-real values.
_MIN_PLAUSIBLE_RPM = 500.0
_MAX_PLAUSIBLE_RPM = 30000.0
_MAX_PLAUSIBLE_SPEED_MS = 250.0


def _is_car_dash_length(data: bytes) -> bool:
    """True when the datagram has exactly the Car Dash frame length.

    Exact, not a minimum: a longer packet is a foreign layout that merely shares
    the header, and treating it as Car Dash would silently read the wrong
    fields. See ``KNOWN_FOREIGN_PACKET_SIZES`` for the layouts this rejects.
    """
    return len(data) == CAR_DASH_PACKET_SIZE


def _is_idle_packet(data: bytes) -> bool:
    """True for the all-zero frame the game sends from menus, pause and loading.

    Forza keeps broadcasting Car Dash packets while you are *not* racing; it
    just stops filling in the fields. Those arrive with ``IsRaceOn`` = 0 and
    everything else zeroed. They are valid Car Dash frames, so they must not be
    reported as a format problem - the dashboard simply has nothing to show yet.

    Length is checked first: anything that is not exactly a Car Dash frame is
    *not* an idle frame, no matter how zeroed its bytes happen to be.
    """
    if not _is_car_dash_length(data):
        return False
    return struct.unpack_from("<i", data, 0)[0] == 0


def looks_like_car_dash(data: bytes) -> bool:
    """Cheap field-level check that a payload really is a Car Dash frame.

    Guards against blindly trusting the offsets on a packet that merely happens
    to be long enough. An idle (menu) frame counts as Car Dash, because that is
    exactly what it is.
    """
    if not _is_car_dash_length(data):
        return False
    if _is_idle_packet(data):
        return True
    max_rpm = struct.unpack_from("<f", data, 8)[0]
    if not _MIN_PLAUSIBLE_RPM <= max_rpm <= _MAX_PLAUSIBLE_RPM:
        return False
    speed = struct.unpack_from("<f", data, 256)[0]
    # NaN fails every comparison, so this rejects it too.
    return 0.0 <= speed <= _MAX_PLAUSIBLE_SPEED_MS


def is_idle_frame(data: bytes) -> bool:
    """Public form of :func:`_is_idle_packet` for the receiver."""
    return _is_idle_packet(data)


def describe_rejected_packet(length: int) -> str:
    """Human-readable reason a packet was dropped, for the UI/log."""
    if length in KNOWN_FOREIGN_PACKET_SIZES:
        return (
            f"Received a {length}-byte {KNOWN_FOREIGN_PACKET_SIZES[length]} packet. "
            "Virtual TCU needs the 324-byte Car Dash format — set Data Out packet "
            "format to Car Dash."
        )
    return (
        f"Received an unrecognised {length}-byte packet (expected 324-byte Car Dash). "
        "Check the Data Out packet format in the game's HUD & Gameplay settings."
    )


def parse_fh6_packet(data: bytes) -> Telemetry | None:
    # Car Dash only, exact length. A foreign layout that merely shares the
    # header would otherwise parse into plausible-looking garbage, and a packet
    # that is long enough but fails the field check is not Car Dash either.
    if not looks_like_car_dash(data):
        return None

    try:
        is_race, session_ts, max_rpm, idle_rpm, cur_rpm = struct.unpack_from("<iIfff", data, 0)
        ax, ay, az = struct.unpack_from("<fff", data, 20)
        vx, vy, vz = struct.unpack_from("<fff", data, 32)
        avx, avy, avz = struct.unpack_from("<fff", data, 44)
        speed, power, torque = struct.unpack_from("<fff", data, 256)
        boost = struct.unpack_from("<f", data, 284)[0]

        accel = data[315]
        brake = data[316]
        clutch = data[317]
        gear = data[319]

        car_ord, car_cls, pi, drivetrain, ncyl = struct.unpack_from("<iiiii", data, 212)
        slip_fl, slip_fr, slip_rl, slip_rr = struct.unpack_from("<ffff", data, 84)
        slip_angle_fl, slip_angle_fr, slip_angle_rl, slip_angle_rr = struct.unpack_from(
            "<ffff", data, 164
        )
        combined_slip_fl, combined_slip_fr, combined_slip_rl, combined_slip_rr = struct.unpack_from(
            "<ffff", data, 180
        )
    except (struct.error, IndexError):
        return None

    is_shifting = gear > 10

    return Telemetry(
        is_race_on=is_race,
        engine_max_rpm=max_rpm,
        current_rpm=cur_rpm,
        accel_x=ax,
        accel_y=ay,
        accel_z=az,
        vel_x=vx,
        vel_y=vy,
        vel_z=vz,
        ang_vel_x=avx,
        ang_vel_y=avy,
        ang_vel_z=avz,
        speed_ms=speed,
        power_w=power,
        torque_nm=torque,
        boost_raw=boost,
        accel_raw=accel,
        brake_raw=brake,
        clutch_raw=clutch,
        gear=gear,
        car_ordinal=car_ord,
        car_class=car_cls,
        pi=pi,
        session_timestamp=session_ts,
        idle_rpm=idle_rpm,
        drivetrain=drivetrain,
        num_cylinders=ncyl,
        slip_fl=slip_fl,
        slip_fr=slip_fr,
        slip_rl=slip_rl,
        slip_rr=slip_rr,
        slip_angle_fl=slip_angle_fl,
        slip_angle_fr=slip_angle_fr,
        slip_angle_rl=slip_angle_rl,
        slip_angle_rr=slip_angle_rr,
        combined_slip_fl=combined_slip_fl,
        combined_slip_fr=combined_slip_fr,
        combined_slip_rl=combined_slip_rl,
        combined_slip_rr=combined_slip_rr,
        is_shifting=is_shifting,
    )
