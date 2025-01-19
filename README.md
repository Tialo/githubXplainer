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
# Start database
docker-compose up -d postgres

# Start API server
uvicorn backend.api.app:app --reload
```

3. **Initialize Repository**
```bash
curl -X POST http://localhost:8000/repos/init \
-H "Content-Type: application/json" \
-d '{"owner": "openai", "repo": "tiktoken"}'
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
