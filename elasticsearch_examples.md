# Elasticsearch API Examples

## Initialize Elasticsearch Indices

Populate Elasticsearch with data from PostgreSQL database.

```bash
curl -X POST http://localhost:8000/elasticsearch/init
```

Example Response:
```json
{
  "status": "success",
  "indices_initialized": 3,
  "message": "Successfully initialized Elasticsearch indices with PostgreSQL data"
}
```

## Search All Content Types

Search across commits, issues, and pull requests.

```bash
curl -X POST http://localhost:8000/search/all \
-H "Content-Type: application/json" \
-d '{
  "repository_id": 1,
  "query": "authentication implementation",
  "from_date": "2024-01-01T00:00:00Z",
  "size": 10
}'
```

Example Response:
```json
{
  "total": 5,
  "took": 0.123,
  "results": [
    {
      "id": 1,
      "type": "commit",
      "title": null,
      "content": "Implement OAuth authentication flow",
      "created_at": "2024-01-15T14:30:00Z",
      "score": 0.8765
    },
    {
      "id": 2,
      "type": "issue",
      "title": "Add JWT Authentication",
      "content": "We need to implement JWT authentication for API endpoints",
      "created_at": "2024-01-20T09:15:00Z",
      "score": 0.7654
    }
  ]
}
```

## Search Specific Content Type

### Search Commits

```bash
curl -X POST http://localhost:8000/search/type/commits \
-H "Content-Type: application/json" \
-d '{
  "repository_id": 1,
  "query": "fix bug",
  "from_date": "2024-01-01T00:00:00Z",
  "size": 2
}'
```

### Search Issues

```bash
curl -X POST http://localhost:8000/search/type/issues \
-H "Content-Type: application/json" \
-d '{
  "repository_id": 1,
  "query": "memory leak",
  "state": "open",
  "labels": ["bug", "high-priority"],
  "from_date": "2024-01-01T00:00:00Z",
  "size": 5
}'
```

### Search Pull Requests

```bash
curl -X POST http://localhost:8000/search/type/pull_requests \
-H "Content-Type: application/json" \
-d '{
  "repository_id": 1,
  "query": "feature implementation",
  "state": "open",
  "base_branch": "main",
  "from_date": "2024-01-01T00:00:00Z",
  "size": 5
}'
```

## Find Similar Content

Find similar issues or pull requests based on text content.

```bash
curl -X POST http://localhost:8000/search/similar \
-H "Content-Type: application/json" \
-d '{
  "repository_id": 1,
  "text": "Error handling in authentication middleware",
  "content_type": "issues",
  "size": 5
}'
```

Example Response:
```json
{
  "total": 3,
  "took": 0.089,
  "similar_items": [
    {
      "id": 15,
      "type": "issue",
      "title": "Improve error handling in auth system",
      "content": "Current error handling in authentication middleware needs improvement...",
      "created_at": "2024-01-25T11:20:00Z",
      "score": 0.9123
    }
  ]
}
```
