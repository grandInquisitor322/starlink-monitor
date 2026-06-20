import numpy as np
from src.telemetry import TelemetryFrame


# Number of standard deviations above baseline to trigger an alert
SIGNAL_DEVIATION_MULTIPLIER = 2.0
LATENCY_DEVIATION_MULTIPLIER = 2.0
PACKET_LOSS_THRESHOLD = 0.3  # 30% packet loss is always suspicious
FREQUENCY_DEVIATION_MHZ = 1.5  # frequency shift threshold


def compute_baseline(frames: list[TelemetryFrame]) -> dict:
    """
    Computes baseline statistics from a set of normal telemetry frames.
    Used to establish what "normal" looks like before anomaly detection.

    Returns: {"signal_mean", "signal_std", "latency_mean", "latency_std",
              "packet_loss_mean", "packet_loss_std", "frequency_mean", "frequency_std"}
    """
    normal_frames = [f for f in frames if not f.is_jammed]

    if len(normal_frames) < 3:
        # Not enough data — use default baselines
        return {
            "signal_mean": -70.0,
            "signal_std": 2.0,
            "latency_mean": 30.0,
            "latency_std": 3.0,
            "packet_loss_mean": 0.1,
            "packet_loss_std": 0.05,
            "frequency_mean": 11700.0,
            "frequency_std": 0.5,
        }

    signals = [f.signal_strength_dbm for f in normal_frames]
    latencies = [f.latency_ms for f in normal_frames]
    losses = [f.packet_loss_pct for f in normal_frames]
    freqs = [f.frequency_mhz for f in normal_frames]

    return {
        "signal_mean": np.mean(signals),
        "signal_std": max(np.std(signals), 0.5),
        "latency_mean": np.mean(latencies),
        "latency_std": max(np.std(latencies), 1.0),
        "packet_loss_mean": np.mean(losses),
        "packet_loss_std": max(np.std(losses), 0.01),
        "frequency_mean": np.mean(freqs),
        "frequency_std": max(np.std(freqs), 0.1),
    }


def score_frame(frame: TelemetryFrame, baseline: dict) -> float:
    """
    Computes an anomaly score for a single telemetry frame.
    Score is the maximum number of standard deviations from baseline
    across all signal parameters.

    Score > 2.0 = suspicious
    Score > 3.0 = likely jammed
    """
    # Signal strength drop (jamming causes signal to drop)
    signal_dev = (baseline["signal_mean"] - frame.signal_strength_dbm) / baseline["signal_std"]

    # Latency spike
    latency_dev = (frame.latency_ms - baseline["latency_mean"]) / baseline["latency_std"]

    # Packet loss spike
    loss_dev = (frame.packet_loss_pct - baseline["packet_loss_mean"]) / baseline["packet_loss_std"]

    # Frequency shift
    freq_dev = abs(frame.frequency_mhz - baseline["frequency_mean"]) / baseline["frequency_std"]

    # Anomaly score is the max deviation across all parameters
    score = max(signal_dev, latency_dev, loss_dev, freq_dev)
    return round(max(score, 0.0), 3)


def detect_anomalies(frames: list[TelemetryFrame], baseline: dict = None) -> list[TelemetryFrame]:
    """
    Runs anomaly detection across all telemetry frames.
    Sets anomaly_score on each frame.
    Returns frames flagged as anomalous (score > SIGNAL_DEVIATION_MULTIPLIER).
    """
    if baseline is None:
        baseline = compute_baseline(frames)

    flagged = []

    for frame in frames:
        frame.anomaly_score = score_frame(frame, baseline)

        if frame.anomaly_score >= SIGNAL_DEVIATION_MULTIPLIER:
            flagged.append(frame)

    return flagged


def summarize_detections(frames: list[TelemetryFrame], flagged: list[TelemetryFrame]) -> dict:
    """
    Summarizes anomaly detection results.
    """
    total = len(frames)
    total_flagged = len(flagged)
    true_positives = sum(1 for f in flagged if f.is_jammed)
    false_positives = sum(1 for f in flagged if not f.is_jammed)
    actual_jammed = sum(1 for f in frames if f.is_jammed)
    missed = actual_jammed - true_positives

    summary = {
        "total_frames": total,
        "flagged": total_flagged,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "missed_detections": missed,
        "actual_jammed": actual_jammed,
        "detection_rate_pct": round(true_positives / actual_jammed * 100, 1) if actual_jammed > 0 else 0.0,
        "false_positive_rate_pct": round(false_positives / (total - actual_jammed) * 100, 1) if (total - actual_jammed) > 0 else 0.0,
    }

    print(f"\n=== Anomaly Detection Summary ===")
    print(f"Total frames:       {total}")
    print(f"Actually jammed:    {actual_jammed}")
    print(f"Flagged:            {total_flagged}")
    print(f"True positives:     {true_positives}")
    print(f"False positives:    {false_positives}")
    print(f"Missed detections:  {missed}")
    print(f"Detection rate:     {summary['detection_rate_pct']}%")
    print(f"False positive rate:{summary['false_positive_rate_pct']}%")

    return summary