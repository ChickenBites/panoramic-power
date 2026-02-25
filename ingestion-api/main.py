import os
import redis
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Energy Data Ingestion API")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
STREAM_NAME = "energy_readings"

# Redis client
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


class EnergyReading(BaseModel):
    site_id: str = Field(..., min_length=1, description="Site identifier")
    device_id: str = Field(..., min_length=1, description="Device identifier")
    power_reading: float = Field(..., description="Power reading in watts")
    timestamp: str = Field(..., min_length=1, description="ISO 8601 timestamp")


class ReadingResponse(BaseModel):
    status: str
    stream_id: str


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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "redis": "disconnected"}


@app.post("/readings", status_code=status.HTTP_201_CREATED, response_model=ReadingResponse)
async def create_reading(reading: EnergyReading):
    """Ingest energy reading and publish to Redis Stream"""
    try:
        # Create the message to add to the stream
        message = {
            "site_id": reading.site_id,
            "device_id": reading.device_id,
            "power_reading": str(reading.power_reading),
            "timestamp": reading.timestamp,
        }
        
        # Add to Redis Stream
        stream_id = redis_client.xadd(STREAM_NAME, message)
        
        logger.info(f"Added reading to stream: {stream_id}")
        
        return ReadingResponse(status="accepted", stream_id=stream_id)
    
    except redis.RedisError as e:
        logger.error(f"Redis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store reading"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
