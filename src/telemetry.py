import numpy as np
from datetime import datetime, timezone
from dataclasses import dataclass, field
from itertools import count


# Baseline signal parameters
BASELINE_SIGNAL_STRENGTH_DBM = -70.0
BASELINE_LATENCY_MS = 30.0
BASELINE_PACKET_LOSS_PCT = 0.1
NOISE_STD = 2.0

# CCSDS 133.0-B Space Packet Protocol constants
CCSDS_VERSION = 0          # Packet Version Number (3 bits) — 0 = Version 1
CCSDS_TYPE_TELEMETRY = 0   # Packet Type — 0 = TM (telemetry), 1 = TC (telecommand)
CCSDS_SEC_HDR_FLAG = 1     # Secondary header present
CCSDS_APID_TELEMETRY = 100 # Application Process ID for this telemetry stream

_sequence_counter = count(start=0)


@dataclass
class CCSDSPrimaryHeader:
    """
    CCSDS 133.0-B Space Packet Protocol — Primary Header (6 bytes / 48 bits).
    Mirrors the structure used in real spacecraft telemetry packets.
    """
    version: int = CCSDS_VERSION                  # 3 bits
    packet_type: int = CCSDS_TYPE_TELEMETRY        # 1 bit (0=TM, 1=TC)
    sec_hdr_flag: int = CCSDS_SEC_HDR_FLAG          # 1 bit
    apid: int = CCSDS_APID_TELEMETRY                # 11 bits — Application Process ID
    sequence_flags: int = 3                         # 2 bits — 3 = unsegmented
    sequence_count: int = 0                         # 14 bits — packet sequence number
    packet_length: int = 0                          # 16 bits — data field length - 1

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "packet_type": "TM" if self.packet_type == 0 else "TC",
            "sec_hdr_flag": self.sec_hdr_flag,
            "apid": self.apid,
            "sequence_flags": self.sequence_flags,
            "sequence_count": self.sequence_count,
            "packet_length": self.packet_length,
        }


@dataclass
class TelemetryFrame:
    """
    A single telemetry reading from a satellite link, wrapped in a
    CCSDS 133.0-B compliant Space Packet structure.

    NIST SP 800-53 AU-3: Content of Audit Records
    CCSDS 133.0-B: Space Packet Protocol
    """
    satellite_name: str
    station_name: str
    timestamp: str
    signal_strength_dbm: float
    latency_ms: float
    packet_loss_pct: float
    frequency_mhz: float
    is_jammed: bool = False
    anomaly_score: float = 0.0
    ccsds_header: CCSDSPrimaryHeader = field(default_factory=CCSDSPrimaryHeader)

    def __post_init__(self):
        # Assign sequence count and packet length per CCSDS spec
        self.ccsds_header.sequence_count = next(_sequence_counter) % 16384  # 14-bit rollover
        # Approximate data field length: 5 float fields (4 bytes each) + 1 bool + timestamp string
        self.ccsds_header.packet_length = (5 * 4) + 1 + len(self.timestamp.encode("utf-8")) - 1


def generate_normal_telemetry(satellite_name: str, station_name: str) -> TelemetryFrame:
    """
    Generates a normal CCSDS-wrapped telemetry frame with realistic noise.
    """
    return TelemetryFrame(
        satellite_name=satellite_name,
        station_name=station_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        signal_strength_dbm=np.random.normal(BASELINE_SIGNAL_STRENGTH_DBM, NOISE_STD),
        latency_ms=np.random.normal(BASELINE_LATENCY_MS, 3.0),
        packet_loss_pct=max(0.0, np.random.normal(BASELINE_PACKET_LOSS_PCT, 0.05)),
        frequency_mhz=np.random.normal(11700.0, 0.5),  # Ku-band downlink
        is_jammed=False,
    )


def inject_jamming(frame: TelemetryFrame, severity: float = 1.0) -> TelemetryFrame:
    """
    Injects jamming anomalies into a telemetry frame.
    severity: 0.0 (mild) to 1.0 (severe)
    """
    frame.signal_strength_dbm -= np.random.uniform(15.0, 40.0) * severity
    frame.latency_ms += np.random.uniform(50.0, 300.0) * severity
    frame.packet_loss_pct += np.random.uniform(0.1, 0.9) * severity
    frame.packet_loss_pct = min(frame.packet_loss_pct, 1.0)
    frame.frequency_mhz += np.random.uniform(-2.0, 2.0) * severity
    frame.is_jammed = True

    return frame


def generate_telemetry_stream(
    handoffs: list[dict],
    num_frames: int = 50,
    jam_probability: float = 0.1,
    jam_severity: float = 0.8,
) -> list[TelemetryFrame]:
    """
    Generates a stream of CCSDS-wrapped telemetry frames for all connected
    ground stations. Randomly injects jamming events based on jam_probability.
    """
    frames = []

    connected = [h for h in handoffs if h["status"] == "connected"]

    if not connected:
        print("[Telemetry] No connected stations — cannot generate telemetry")
        return frames

    for _ in range(num_frames):
        handoff = connected[np.random.randint(len(connected))]
        sat_name = handoff["serving_satellite"]
        station_name = handoff["station"]

        frame = generate_normal_telemetry(sat_name, station_name)

        if np.random.random() < jam_probability:
            frame = inject_jamming(frame, severity=jam_severity)

        frames.append(frame)

    jammed_count = sum(1 for f in frames if f.is_jammed)
    print(f"[Telemetry] Generated {len(frames)} CCSDS frames | Jammed: {jammed_count} ({round(jammed_count/len(frames)*100, 1)}%)")

    return frames


def frames_to_dicts(frames: list[TelemetryFrame]) -> list[dict]:
    """
    Converts TelemetryFrame objects (including CCSDS header) to dicts
    for JSON serialization or DynamoDB logging.
    """
    return [
        {
            "ccsds_header": f.ccsds_header.to_dict(),
            "satellite_name": f.satellite_name,
            "station_name": f.station_name,
            "timestamp": f.timestamp,
            "signal_strength_dbm": round(f.signal_strength_dbm, 2),
            "latency_ms": round(f.latency_ms, 2),
            "packet_loss_pct": round(f.packet_loss_pct, 4),
            "frequency_mhz": round(f.frequency_mhz, 3),
            "is_jammed": f.is_jammed,
            "anomaly_score": round(f.anomaly_score, 4),
        }
        for f in frames
    ]