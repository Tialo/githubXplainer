# GitHub Xplainer

Analyze GitHub repositories and generate insights using AI.

## Quick Start

1. **Setup Environment**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

2. **Start Services (in this exact order)**
```bash
# 1. Start infrastructure services first
docker-compose up postgres elasticsearch kafka kafka-ui

# 3. Start RQ worker (in a separate terminal)
# RQ must be started before the API server since it processes the background tasks
python -m backend.tasks.summary_tasks

# 4. Finally, start the API server (in another separate terminal)
uvicorn backend.api.app:app --reload
```

3. **Initialize Repository**
```bash
curl -X POST http://localhost:8000/repos/init \
-H "Content-Type: application/json" \
-d '{"owner": "openai", "repo": "tiktoken"}'


curl -X POST http://localhost:8000/repos/init \
-H "Content-Type: application/json" \
-d '{"owner": "Tialo", "repo": "githubXplainer"}'
```

```bash
# init
curl -X POST http://localhost:8000/elasticsearch/init

# drop
curl -X POST http://localhost:8000/elasticsearch/clear

curl -X DELETE http://localhost:8000/repos/delete \
-H "Content-Type: application/json" \
-d '{"owner": "Tialo", "repo": "githubXplainer"}'
```

```bash
# Drop volumes
docker-compose down -v
```

## Development

```bash
# Format code
poetry run black backend/
poetry run isort backend/

# Run tests
poetry run pytest
```

## Troubleshooting

- **Database issues**: Check `docker-compose ps` and database credentials
- **GitHub API**: Verify token in `.env` and rate limits
- **Service errors**: Check `logs/app.log` for details
- **RQ worker**: Verify Redis connection and check RQ logs with `python -m backend.tasks.worker --loglevel=debug`

## API Documentation

Browse OpenAPI docs at http://localhost:8000/docs

## Monitoring

### RQ Monitoring
Access the Flower dashboard at http://localhost:5555 to monitor:
- Task progress and history
- Worker status
- Real-time statistics
- Task graphs and metrics

### Kafka Monitoring
Access the Kafka UI dashboard at http://localhost:8080 to monitor:
- Topic management and browsing
- Consumer groups
- Message browsing
- Cluster state
- Performance metrics

## Kafka Setup

The application uses Kafka for message queuing with two main topics:
- `readme`: For processing README file changes
- `commit`: For processing commit information

### Usage Example

```typescript
import { KafkaService, TOPICS } from './kafka/KafkaService';

// Initialize service
const kafkaService = new KafkaService();
await kafkaService.initialize();

// Create a consumer
const consumer = await kafkaService.createConsumer('my-group');

// Subscribe to topics
await kafkaService.subscribeToTopic(consumer, TOPICS.README, async (message) => {
  console.log('Received README update:', message);
});

// Publish a message
await kafkaService.publishMessage(TOPICS.COMMIT, {
  id: '123',
  message: 'Initial commit'
});
```
