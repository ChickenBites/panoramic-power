# Energy Microservices

A cloud-native energy data ingestion and processing system built with Python/FastAPI, Redis Streams, Kubernetes, and KEDA autoscaling.

## Architecture

```
┌─────────────┐    XADD     ┌──────────────┐    XREADGROUP    ┌─────────────────┐
│ Ingestion   │ ──────────► │   Redis      │ ──────────────► │  Processing     │
│   API        │   Stream   │   Stream     │   Consumer Group │  Service        │
│ (Port 8000)  │             │"energy_readings"                 │  (Port 8001)    │
└─────────────┘             └──────────────┘                  └────────┬────────┘
                                                                        │
                                                                        │ RPUSH
                                                                        ▼
                                                              ┌─────────────────┐
                                                              │   Redis List    │
                                                              │site_readings:{id}│
                                                              └─────────────────┘
```

## Components

### 1. Ingestion API (FastAPI)
- **Port**: 8000
- **Endpoints**:
  - `POST /readings` - Submit energy readings to Redis Stream
  - `GET /health` - Health check endpoint
- **Environment Variables**:
  - `REDIS_HOST` - Redis host (default: localhost)
  - `REDIS_PORT` - Redis port (default: 6379)

### 2. Processing Service (FastAPI)
- **Port**: 8001
- **Endpoints**:
  - `GET /sites/{site_id}/readings` - Get all readings for a site
  - `GET /health` - Health check endpoint
- **Features**:
  - Consumes messages from Redis Stream using consumer groups
  - Stores processed readings in Redis lists keyed by site_id
  - Acknowledges processed messages (XACK)
- **Environment Variables**:
  - `REDIS_HOST` - Redis host (default: localhost)
  - `REDIS_PORT` - Redis port (default: 6379)

### 3. Frontend (Bonus)
- Simple HTML/JS dashboard for submitting and viewing readings
- **Port**: 3000

### 4. Redis
- Used as both message broker (Streams) and data store
- Consumer group: `processing_group`

### 5. KEDA Autoscaling
- Scales processing service based on pending entries in Redis Stream
- Configurable min/max replicas and threshold

## Prerequisites

- Docker & Docker Compose (for local development)
- Kubernetes cluster (kind, minikube, or cloud)
- Helm 3
- KEDA (for autoscaling)

## Local Development

### Using Docker Compose

1. Start all services:
```bash
cd energy-microservices
docker-compose up -d
```

2. Check service health:
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
```

3. Submit a reading:
```bash
curl -X POST http://localhost:8000/readings \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "site-001",
    "device_id": "meter-42",
    "power_reading": 1500.5,
    "timestamp": "2024-01-15T10:30:00Z"
  }'
```

4. Fetch readings for a site:
```bash
curl http://localhost:8001/sites/site-001/readings
```

5. Access the frontend:
```bash
open http://localhost:3000
```

### Manual Setup

1. Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

2. Start Ingestion API:
```bash
cd ingestion-api
pip install -r requirements.txt
python main.py
```

3. Start Processing Service:
```bash
cd processing-service
pip install -r requirements.txt
python main.py
```

## Kubernetes Deployment

### Using Helm

1. Add dependencies (optional - we have embedded Redis):
```bash
# If using external Redis chart
helm repo add bitnami https://charts.bitnami.com/bitnami
```

2. Deploy the chart:
```bash
# Deploy with default values
helm install energy-microservices ./helm-chart --namespace energy-system --create-namespace

# Or with custom values
helm install energy-microservices ./helm-chart \
  --namespace energy-system \
  --create-namespace \
  --set ingestionApi.image.repository=my-registry/ingestion-api \
  --set processingService.image.repository=my-registry/processing-service
```

3. Enable KEDA autoscaling:
```bash
helm upgrade energy-microservices ./helm-chart \
  --namespace energy-system \
  --set keda.enabled=true
```

### Using Kind (Local Development)

1. Create a kind cluster:
```bash
kind create cluster --name energy-cluster
```

2. Install KEDA:
```bash
kubectl apply -f https://github.com/kedacore/keda/releases/download/v2.14.0/keda-2.14.0.yaml
```

3. Load Docker images into kind:
```bash
kind load docker-image ingestion-api:latest --name energy-cluster
kind load docker-image processing-service:latest --name energy-cluster
```

4. Deploy:
```bash
kubectl apply -f ./helm-chart/templates/
```

### Verify Deployment

```bash
# Check pods
kubectl get pods -n energy-system

# Check services
kubectl get services -n energy-system

# Check logs
kubectl logs -n energy-system -l app=ingestion-api
kubectl logs -n energy-system -l app=processing-service
```

## CI/CD

The project includes a GitHub Actions workflow (`.github/workflows/ci-cd.yaml`) that:

1. **Lints** Python code with flake8
2. **Validates** Helm charts with `helm lint` and `helm template`
3. **Builds** Docker images for all services
4. **Deploys** to Kubernetes on push to main/master

### Setup Secrets

For deployment, add the following secrets to your GitHub repository:
- `KUBECONFIG` - Base64 encoded kubeconfig file

## Helm Chart Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `assignmentId` | Unique assignment identifier | `DE43B346-214A-4394-BB61-BC4E5874A95A` |
| `global.redis.host` | Redis hostname | `redis-master` |
| `global.redis.port` | Redis port | `6379` |
| `ingestionApi.replicaCount` | Number of ingestion API pods | `1` |
| `processingService.replicaCount` | Number of processing service pods | `1` |
| `keda.enabled` | Enable KEDA autoscaling | `false` |
| `keda.scaledObject.minReplicaCount` | Minimum replicas | `1` |
| `keda.scaledObject.maxReplicaCount` | Maximum replicas | `10` |
| `keda.scaledObject.threshold` | Scaling threshold | `5` |

## Design Decisions

1. **Redis Streams**: Chosen over traditional message queues for:
   - Native consumer group support
   - Message persistence and replay capability
   - KEDA integration for event-driven autoscaling

2. **Consumer Groups**: Used for:
   - Load balancing across processing instances
   - Message acknowledgment (XACK)
   - At-least-once delivery guarantee

3. **Redis Lists for Storage**: Using Redis lists keyed by `site_readings:{site_id}` for:
   - Simple implementation
   - O(1) append operations
   - O(n) retrieval (acceptable for this use case)

4. **KEDA Redis Trigger**: Scales based on `pendingEntriesCount` rather than stream length, ensuring scaling responds to actual unprocessed work.

## Trade-offs

1. **Single-threaded Processing**: The processing service uses a single background thread. For higher throughput, consider:
   - Multiple worker threads
   - Async processing with asyncio
   - Multiple consumer group consumers

2. **No Data Retention Policy**: Currently, readings accumulate indefinitely. Consider:
   - TTL-based expiration
   - Size-based trimming (XTRIM)

3. **No Encryption**: Redis communication is unencrypted. For production:
   - Enable Redis TLS
   - Use Redis authentication
   - Enable network policies

## License

MIT
