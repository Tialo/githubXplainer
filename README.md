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
docker-compose up
uvicorn backend.api.app:app --reload --log-level=info
npm run dev
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

curl -X POST http://localhost:8000/search/faiss \
-H "Content-Type: application/json" \
-d '{"query": "what where last bugfixes", "owner": "openai", "name": "tiktoken"}'

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

## API Documentation

Browse OpenAPI docs at http://localhost:8000/docs
