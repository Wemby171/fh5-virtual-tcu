from dataclasses import dataclass

from virtual_tcu.telemetry.car_key import (
    CarKey,
    CarKeyBase,
    car_key_base,
    compute_tune_signature,
    make_car_key,
)

# Car Dash packet size. Forza Horizon 5 and Forza Horizon 6 emit the same
# fixed layout (verified field-by-field against the Horizon packet format), so
# one set of parser offsets serves either game.
CAR_DASH_PACKET_SIZE = 324
FH5_CAR_DASH_PACKET_SIZE = CAR_DASH_PACKET_SIZE
# Historical name, kept as an alias so existing imports keep working. Both
# Horizon titles use the same 324-byte Car Dash frame.
FH6_PACKET_SIZE = CAR_DASH_PACKET_SIZE

# Motorsport / Sled layouts share the head of this struct but drop the
# Horizon-only block, so every field from Speed onward moves 12 bytes earlier.
SLED_PACKET_SIZE = 311
MOTORSPORT_DASH_PACKET_SIZE = 331

# Lengths worth naming in diagnostics when a packet cannot be parsed.
KNOWN_FOREIGN_PACKET_SIZES = {
    SLED_PACKET_SIZE: "Forza Motorsport / Sled (311 B)",
    MOTORSPORT_DASH_PACKET_SIZE: "Forza Motorsport Dash (331 B)",
}


@dataclass
class Telemetry:
    is_race_on: int = 0
    engine_max_rpm: float = 8000.0
    current_rpm: float = 0.0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    vel_x: float = 0.0
    vel_y: float = 0.0
    vel_z: float = 0.0
    ang_vel_x: float = 0.0
    ang_vel_y: float = 0.0
    ang_vel_z: float = 0.0
    speed_ms: float = 0.0
    power_w: float = 0.0
    torque_nm: float = 0.0
    boost_raw: float = 0.0
    accel_raw: int = 0
    brake_raw: int = 0
    clutch_raw: int = 0
    gear: int = 0
    car_ordinal: int = 0
    car_class: int = 0
    pi: int = 0
    session_timestamp: int = 0
    idle_rpm: float = 0.0
    drivetrain: int = 0
    num_cylinders: int = 0
    slip_fl: float = 0.0
    slip_fr: float = 0.0
    slip_rl: float = 0.0
    slip_rr: float = 0.0
    slip_angle_fl: float = 0.0
    slip_angle_fr: float = 0.0
    slip_angle_rl: float = 0.0
    slip_angle_rr: float = 0.0
    combined_slip_fl: float = 0.0
    combined_slip_fr: float = 0.0
    combined_slip_rl: float = 0.0
    combined_slip_rr: float = 0.0
    is_shifting: bool = False
    # Set by TCULogic — selects the active profile tune slot for this session.
    profile_tune_id: int = 0

    @property
    def rear_slip(self) -> float:
        return max(abs(self.slip_rl), abs(self.slip_rr))

    @property
    def front_slip(self) -> float:
        return max(abs(self.slip_fl), abs(self.slip_fr))

    @property
    def speed_kmh(self) -> float:
        if 0.0 <= self.speed_ms < 200.0:
            return self.speed_ms * 3.6
        mag = (self.vel_x**2 + self.vel_y**2 + self.vel_z**2) ** 0.5
        return mag * 3.6

    @property
    def speed_effective_ms(self) -> float:
        if 0.0 <= self.speed_ms < 200.0:
            return self.speed_ms
        return (self.vel_x**2 + self.vel_y**2 + self.vel_z**2) ** 0.5

    @property
    def rpm_pct(self) -> float:
        return self.current_rpm / self.engine_max_rpm if self.engine_max_rpm > 0 else 0.0

    @property
    def throttle(self) -> float:
        return self.accel_raw / 255.0

    @property
    def brake(self) -> float:
        return self.brake_raw / 255.0

    @property
    def car_key_base(self) -> CarKeyBase:
        return car_key_base(self)

    @property
    def tune_signature(self) -> int:
        """Engine/drivetrain fingerprint — changes when those parts of the build change."""
        return compute_tune_signature(self)

    @property
    def car_key(self) -> CarKey:
        """Composite vehicle + tune slot identifier for learning and profiles.

        ``tune_id`` defaults to ``tune_signature``; TCULogic may assign a new
        ``profile_tune_id`` after detecting stale gear-ratio data (e.g. same PI
        but different gearing)."""
        tune_id = self.profile_tune_id or self.tune_signature
        return make_car_key(self.car_key_base, tune_id)

    @property
    def drivetrain_name(self) -> str:
        return {0: "FWD", 1: "RWD", 2: "AWD"}.get(self.drivetrain, "—")
