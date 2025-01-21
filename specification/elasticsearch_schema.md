# Elasticsearch Schema Specification

## Overview
This document outlines the Elasticsearch indices and mappings required to support the GitHub repository analysis system. The schema is designed to facilitate efficient text search, analysis, and retrieval of repository content.

## Indices Structure

### 1. commits_index

```json
{
  "mappings": {
    "properties": {
      "commit_hash": { "type": "keyword" },
      "message": { 
        "type": "text",
        "analyzer": "english",
        "fields": {
          "keyword": { "type": "keyword", "ignore_above": 256 }
        }
      },
      "summary": {
        "type": "text",
        "analyzer": "english"
      },
      "analysis": {
        "type": "object",
        "properties": {
          "type": { "type": "keyword" },
          "scope": { "type": "keyword" },
          "impact_level": { "type": "keyword" }
        }
      },
      "file_changes": {
        "type": "nested",
        "properties": {
          "file_path": { "type": "keyword" },
          "change_type": { "type": "keyword" },
          "content_diff": { "type": "text" }
        }
      },
      "metadata": {
        "properties": {
          "author": { "type": "keyword" },
          "date": { "type": "date" },
          "repository_id": { "type": "keyword" }
        }
      }
    }
  }
}
```

### 2. issues_index

```json
{
  "mappings": {
    "properties": {
      "issue_number": { "type": "keyword" },
      "title": {
        "type": "text",
        "analyzer": "english",
        "fields": {
          "keyword": { "type": "keyword", "ignore_above": 256 }
        }
      },
      "body": {
        "type": "text",
        "analyzer": "english"
      },
      "summary": {
        "type": "text",
        "analyzer": "english"
      },
      "comments": {
        "type": "nested",
        "properties": {
          "author": { "type": "keyword" },
          "content": { "type": "text", "analyzer": "english" },
          "date": { "type": "date" }
        }
      },
      "analysis": {
        "type": "object",
        "properties": {
          "category": { "type": "keyword" },
          "priority": { "type": "keyword" },
          "resolution_status": { "type": "keyword" }
        }
      },
      "metadata": {
        "properties": {
          "state": { "type": "keyword" },
          "created_at": { "type": "date" },
          "closed_at": { "type": "date" },
          "labels": { "type": "keyword" },
          "repository_id": { "type": "keyword" }
        }
      }
    }
  }
}
```

### 3. pull_requests_index

```json
{
  "mappings": {
    "properties": {
      "pr_number": { "type": "keyword" },
      "title": {
        "type": "text",
        "analyzer": "english",
        "fields": {
          "keyword": { "type": "keyword", "ignore_above": 256 }
        }
      },
      "description": {
        "type": "text",
        "analyzer": "english"
      },
      "summary": {
        "type": "text",
        "analyzer": "english"
      },
      "reviews": {
        "type": "nested",
        "properties": {
          "reviewer": { "type": "keyword" },
          "comment": { "type": "text", "analyzer": "english" },
          "state": { "type": "keyword" },
          "date": { "type": "date" }
        }
      },
      "analysis": {
        "type": "object",
        "properties": {
          "change_type": { "type": "keyword" },
          "impact_scope": { "type": "keyword" },
          "review_sentiment": { "type": "keyword" }
        }
      },
      "metadata": {
        "properties": {
          "state": { "type": "keyword" },
          "created_at": { "type": "date" },
          "merged_at": { "type": "date" },
          "base_branch": { "type": "keyword" },
          "head_branch": { "type": "keyword" },
          "repository_id": { "type": "keyword" }
        }
      }
    }
  }
}
```

## Usage Patterns

### 1. Commit Analysis
- Search through commit messages and diffs to identify patterns
- Group related commits by analyzing message content and changed files
- Track implementation approaches for specific features

### 2. Issue Analysis
- Identify common problems and their solutions
- Track discussion threads and resolution patterns
- Categorize issues by type and priority

### 3. Pull Request Analysis
- Analyze code review patterns and feedback
- Track implementation decisions and their rationale
- Monitor code quality discussions

## Query Examples

### 1. Feature Implementation Search
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "authentication implementation",
            "fields": ["commits.message", "pulls.description", "issues.body"]
          }
        },
        {
          "range": {
            "metadata.created_at": {
              "gte": "now-6M"
            }
          }
        }
      ]
    }
  }
}
```

### 2. Problem Resolution Search
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "issues.analysis.category": "bug"
          }
        },
        {
          "exists": {
            "field": "issues.metadata.closed_at"
          }
        }
      ]
    }
  }
}
```

## Integration with Vector Search

The Elasticsearch indices will be used in conjunction with vector embeddings to provide comprehensive search capabilities:

1. Text-based search using Elasticsearch for initial filtering
2. Vector similarity search for semantic relevance
3. Combined scoring for final result ranking

## Performance Considerations

1. **Indexing Strategy**
   - Bulk indexing during repository initialization
   - Real-time updates for new content
   - Periodic reindexing for updated analysis

2. **Query Optimization**
   - Use filter context where possible
   - Implement result caching
   - Paginate large result sets

3. **Storage Optimization**
   - Index only necessary fields
   - Use keyword fields for exact matches
   - Implement field data limits

## Maintenance

1. **Index Management**
   - Monthly reindexing schedule
   - Regular backup of index data
   - Monitoring of index size and performance

2. **Data Cleanup**
   - Archive old, unused data
   - Remove duplicate entries
   - Optimize index periodically
