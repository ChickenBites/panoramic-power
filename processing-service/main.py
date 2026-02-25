import os
import json
import uuid
import threading
import time
import redis
from fastapi import FastAPI, HTTPException, status, Request
from pydantic import BaseModel
from typing import List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Energy Data Processing Service")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
STREAM_NAME = "energy_readings"
CONSUMER_GROUP = "processing_group"
CONSUMER_NAME = f"consumer-{uuid.uuid4().hex[:8]}"

# Redis client
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


class StoredReading(BaseModel):
    stream_id: str
    site_id: str
    device_id: str
    power_reading: float
    timestamp: str


class ReadingsResponse(BaseModel):
    site_id: str
    readings: List[StoredReading]


# Manual CORS handler
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    # Handle OPTIONS preflight request directly
    if request.method == "OPTIONS":
        origin = request.headers.get("origin")
        if origin:
            from fastapi.responses import Response
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                    "Vary": "Origin",
                }
            )
    
    response = await call_next(request)
    
    # Get origin from request headers
    origin = request.headers.get("origin")
    
    # Add CORS headers if origin is present
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Vary"] = "Origin"
    
    return response


def setup_consumer_group():
    """Create consumer group if it doesn't exist"""
    try:
        # Try to create the consumer group
        # Using 0-0 to read from the beginning of the stream
        redis_client.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
        logger.info(f"Created consumer group: {CONSUMER_GROUP}")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.info(f"Consumer group {CONSUMER_GROUP} already exists")
        else:
            raise


def process_messages():
    """Background thread to process messages from the stream"""
    logger.info(f"Starting message processor with consumer: {CONSUMER_NAME}")
    
    while True:
        try:
            # Read messages from the stream
            # Using XREADGROUP with BLOCK for non-blocking reads
            messages = redis_client.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {STREAM_NAME: ">"},
                count=10,
                block=5000
            )
            
            if not messages:
                continue
            
            for stream_name, stream_messages in messages:
                for msg_id, msg_data in stream_messages:
                    try:
                        # Parse the message
                        reading = {
                            "stream_id": msg_id,
                            "site_id": msg_data.get("site_id", ""),
                            "device_id": msg_data.get("device_id", ""),
                            "power_reading": float(msg_data.get("power_reading", 0)),
                            "timestamp": msg_data.get("timestamp", ""),
                        }
                        
                        # Store in Redis list keyed by site_id
                        site_id = reading["site_id"]
                        if site_id:
                            # Use a Redis list with site_id as key
                            key = f"site_readings:{site_id}"
                            redis_client.rpush(key, json.dumps(reading))
                            logger.info(f"Stored reading for site {site_id}: {msg_id}")
                        
                        # Acknowledge the message
                        redis_client.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
                        logger.info(f"Acknowledged message: {msg_id}")
                        
                    except Exception as e:
                        logger.error(f"Error processing message {msg_id}: {e}")
                        # Still acknowledge to avoid infinite retries
                        redis_client.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
        
        except Exception as e:
            logger.error(f"Error in message processor: {e}")
            time.sleep(5)


@app.on_event("startup")
async def startup_event():
    """Initialize consumer group and start background processor"""
    setup_consumer_group()
    
    # Start background thread for processing
    processor_thread = threading.Thread(target=process_messages, daemon=True)
    processor_thread.start()
    logger.info("Background message processor started")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected", "consumer": CONSUMER_NAME}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "redis": "disconnected"}


@app.get("/sites/{site_id}/readings", response_model=ReadingsResponse)
async def get_site_readings(site_id: str):
    """Get all readings for a specific site"""
    try:
        key = f"site_readings:{site_id}"
        
        # Get all readings from the list
        readings_raw = redis_client.lrange(key, 0, -1)
        
        readings = []
        for reading_json in readings_raw:
            try:
                reading = json.loads(reading_json)
                readings.append(StoredReading(**reading))
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding reading: {e}")
        
        logger.info(f"Retrieved {len(readings)} readings for site {site_id}")
        return ReadingsResponse(site_id=site_id, readings=readings)
    
    except redis.RedisError as e:
        logger.error(f"Redis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve readings"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
