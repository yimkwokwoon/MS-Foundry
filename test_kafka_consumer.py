import json
import signal
import sys
import time
from azure.eventhub import EventHubConsumerClient
from azure.identity import DefaultAzureCredential

# ============================================================
# CONFIG — Fill in your Event Hub details
# ============================================================
EVENTHUB_NAMESPACE = "foundry-log-ea"       # your namespace name
EVENTHUB_NAME = "foundry-log-eh"            # your event hub name
CONSUMER_GROUP = "cg-onperm-kafka"          # your consumer group

# ============================================================
# Graceful shutdown
# ============================================================
running = True
msg_count = 0

def signal_handler(sig, frame):
    global running
    print("\nShutting down...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

# ============================================================
# Event handler — called for each batch of events
# ============================================================
def on_event(partition_context, event):
    global msg_count

    if event is None:
        return

    msg_count += 1
    value = event.body_as_str()

    try:
        data = json.loads(value)

        # Azure diagnostic logs are wrapped in {"records": [...]}
        if "records" in data:
            for record in data["records"]:
                print(f"\n{'─' * 60}")
                print(f"Message #{msg_count} | Partition: {partition_context.partition_id} | Offset: {event.offset}")
                print(f"   Time:      {record.get('time', 'N/A')}")
                print(f"   Category:  {record.get('category', 'N/A')}")
                print(f"   Operation: {record.get('operationName', 'N/A')}")
                print(f"   Result:    {record.get('resultType', 'N/A')}")
                print(f"   Resource:  {record.get('resourceId', 'N/A')}")
                props = record.get("properties", {})
                if props:
                    print(f"   Properties:")
                    for k, v in props.items():
                        print(f"      {k}: {v}")
        else:
            print(f"\nMessage #{msg_count}: {json.dumps(data, indent=2)[:500]}")

    except json.JSONDecodeError:
        print(f"\nMessage #{msg_count} (raw): {value[:500]}")

    # Update checkpoint so we don't re-read these events
    partition_context.update_checkpoint(event)

def on_error(partition_context, error):
    if partition_context:
        print(f"Error on partition {partition_context.partition_id}: {error}")
    else:
        print(f"Error: {error}")

def on_partition_initialize(partition_context):
    print(f"Partition {partition_context.partition_id} initialized")

def on_partition_close(partition_context, reason):
    print(f"Partition {partition_context.partition_id} closed: {reason}")

# ============================================================
# Main
# ============================================================
def main():
    # Use DefaultAzureCredential (Entra ID) for authentication
    # Falls back to: az login > managed identity > env vars
    credential = DefaultAzureCredential()

    print("=" * 60)
    print(f"Connected to: {EVENTHUB_NAMESPACE}.servicebus.windows.net")
    print(f"Event Hub: {EVENTHUB_NAME}")
    print(f"Consumer Group: {CONSUMER_GROUP}")
    print(f"Auth: DefaultAzureCredential (Entra ID)")
    print(f"Waiting for messages... (Ctrl+C to stop)")
    print("=" * 60)

    client = EventHubConsumerClient(
        fully_qualified_namespace=f"{EVENTHUB_NAMESPACE}.servicebus.windows.net",
        eventhub_name=EVENTHUB_NAME,
        consumer_group=CONSUMER_GROUP,
        credential=credential,
    )

    try:
        with client:
            client.receive(
                on_event=on_event,
                on_error=on_error,
                on_partition_initialize=on_partition_initialize,
                on_partition_close=on_partition_close,
                starting_position="-1",  # from beginning
            )
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\nDone. Total messages received: {msg_count}")

if __name__ == "__main__":
    main()
