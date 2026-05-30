# Redis Messaging

## Purpose
Standard patterns for inter-service communication using Redis pub/sub and streams.

## Pub/Sub for Broadcast Events
Fire-and-forget event broadcasting. No delivery guarantees — subscribers miss messages if not connected.

### Publishing Events
```python
import json
import redis.asyncio as redis

class MessageBus:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def publish(self, channel: str, payload: dict):
        await self.redis.publish(channel, json.dumps(payload))

# Usage
bus = MessageBus("redis://localhost:6379")
await bus.publish("data.synced", {
    "asset_id": 1,
    "candle_count": 5,
    "timestamp": "2024-01-01T12:00:00Z"
})
```

### Subscribing to Events
```python
    async def subscribe(self, channels: list[str], callback):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(*channels)
        async for message in pubsub.listen():
            if message["type"] == "message":
                payload = json.loads(message["data"])
                await callback(message["channel"], payload)

# Usage
async def handle_event(channel: str, payload: dict):
    print(f"Received {channel}: {payload}")

await bus.subscribe(["data.synced", "features.ready"], handle_event)
```

## Streams for Request/Response
Persistent, reliable messaging with correlation IDs. Used for CLI commands and health checks.

### Publishing Requests
```python
class RequestResponse:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def send_request(self, stream: str, data: dict, reply_to: str, timeout: float = 10.0) -> dict:
        import uuid
        correlation_id = str(uuid.uuid4())
        
        # Add request to stream
        await self.redis.xadd(stream, {
            "correlation_id": correlation_id,
            "reply_to": reply_to,
            "data": json.dumps(data)
        })

        # Wait for reply
        reply_stream = f"{reply_to}:{correlation_id}"
        start = "0"
        for _ in range(int(timeout * 10)):  # poll every 100ms
            messages = await self.redis.xread({reply_stream: start}, count=1, block=100)
            if messages:
                _, entries = messages[0]
                for _, entry in entries:
                    if entry.get("correlation_id") == correlation_id:
                        return json.loads(entry["data"])
            start = "$"
        
        raise TimeoutError(f"Request to {stream} timed out after {timeout}s")
```

### Processing Requests and Sending Replies
```python
    async def listen_requests(self, stream: str, handler):
        last_id = "0"
        while True:
            messages = await self.redis.xread({stream: last_id}, count=10, block=1000)
            if messages:
                _, entries = messages[0]
                for msg_id, entry in entries:
                    last_id = msg_id
                    data = json.loads(entry["data"])
                    reply_to = entry["reply_to"]
                    correlation_id = entry["correlation_id"]
                    
                    # Process request
                    response = await handler(data)
                    
                    # Send reply
                    reply_stream = f"{reply_to}:{correlation_id}"
                    await self.redis.xadd(reply_stream, {
                        "correlation_id": correlation_id,
                        "data": json.dumps(response)
                    })
```

## Topic Naming Convention
- Events: `domain.action` (e.g., `data.synced`, `features.ready`)
- Requests: `domain.action.request` (e.g., `train.start.request`)
- Replies: `domain.action.reply` (e.g., `train.start.reply`)
- Heartbeats: `heartbeat.<service-name>`
