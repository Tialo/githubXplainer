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

2. **Start Services**
```bash
# Start infrastructure services
docker-compose up -d postgres elasticsearch redis flower

# Start Celery worker (in a separate terminal)
celery -A backend.tasks.worker.celery_app worker -Q summarization --concurrency=1 --loglevel=info

# Start API server (in another separate terminal)
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
- **Celery worker**: Verify Redis connection and check celery logs with `celery -A backend.tasks.worker worker --loglevel=debug`

## API Documentation

Browse OpenAPI docs at http://localhost:8000/docs

## Monitoring

### Celery Monitoring
Access the Flower dashboard at http://localhost:5555 to monitor:
- Task progress and history
- Worker status
- Real-time statistics
- Task graphs and metrics
