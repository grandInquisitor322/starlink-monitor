import boto3
import os


TOPIC_NAME = "starlink-jamming-alerts"
DEFAULT_REGION = "us-east-1"


def get_sns_client(region: str = DEFAULT_REGION):
    return boto3.client("sns", region_name=region)


def create_topic(region: str = DEFAULT_REGION) -> str:
    """
    Creates the SNS topic if it doesn't exist and returns the ARN.
    NIST SP 800-53 IR-6: Incident Reporting
    """
    client = get_sns_client(region)
    response = client.create_topic(Name=TOPIC_NAME)
    return response["TopicArn"]


def subscribe_email(topic_arn: str, email: str, region: str = DEFAULT_REGION) -> str:
    """
    Subscribes an email address to the jamming alert topic.
    """
    client = get_sns_client(region)
    response = client.subscribe(
        TopicArn=topic_arn,
        Protocol="email",
        Endpoint=email,
    )
    return response["SubscriptionArn"]


def send_jamming_alert(topic_arn: str, flagged: list, scan_id: str, region: str = DEFAULT_REGION):
    """
    Sends an SNS alert when jamming events are detected.
    NIST SP 800-53 IR-4: Incident Handling
    NIST SP 800-53 IR-6: Incident Reporting
    NIST SP 800-53 SI-4: System Monitoring
    """
    if not flagged:
        return

    client = get_sns_client(region)

    subject = f"[ALERT] Starlink Jamming Detected — {len(flagged)} events ({scan_id})"

    # Group alerts by station
    by_station = {}
    for f in flagged:
        by_station.setdefault(f.station_name, []).append(f)

    lines = [
        f"Starlink jamming detection alert",
        f"Scan ID: {scan_id}",
        f"Total jamming events detected: {len(flagged)}",
        f"",
        f"Affected stations:",
    ]

    for station, events in by_station.items():
        avg_signal = sum(e.signal_strength_dbm for e in events) / len(events)
        max_score = max(e.anomaly_score for e in events)
        satellites = list(set(e.satellite_name for e in events))
        lines.append(f"  {station}: {len(events)} events | avg signal={round(avg_signal, 1)} dBm | max score={max_score}")
        lines.append(f"    Affected satellites: {', '.join(satellites[:3])}")

    lines += [
        f"",
        f"NIST SP 800-53 Controls: IR-4, IR-6, SI-4",
        f"Recommended action: Investigate signal interference source and switch to backup frequencies.",
    ]

    message = "\n".join(lines)

    client.publish(
        TopicArn=topic_arn,
        Subject=subject,
        Message=message,
    )

    print(f"[SNS] Jamming alert sent for scan {scan_id} — {len(flagged)} events across {len(by_station)} stations")


def setup_alerts(email: str, region: str = DEFAULT_REGION) -> str:
    """
    One-time setup — creates SNS topic and subscribes email.
    Returns the topic ARN.
    """
    topic_arn = create_topic(region)
    subscribe_email(topic_arn, email, region)
    print(f"[SNS] Topic created: {TOPIC_NAME}")
    print(f"[SNS] Subscribed: {email}")
    print(f"[SNS] Check your inbox and confirm the subscription.")
    return topic_arn