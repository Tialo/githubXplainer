from datetime import datetime, timezone
from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Column
from backend.models.base import Base

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner = Column(String)
    name = Column(String)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    default_branch = Column(String)
    stars_count = Column(Integer)
    forks_count = Column(Integer)
    is_initialized = Column(Boolean, default=False)

    @classmethod
    def from_github_data(cls, data: dict):
        owner, name = data["full_name"].split("/")
        return cls(
            github_id=data["id"],
            owner=owner,
            name=name,
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            default_branch=data["default_branch"],
            stars_count=data["stargazers_count"],
            forks_count=data["forks_count"],
            is_initialized=False
        )

class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    github_sha = Column(String, unique=True)
    message = Column(String)
    author_name = Column(String)
    author_email = Column(String)
    authored_date = Column(DateTime(timezone=True))
    committer_name = Column(String)
    committer_email = Column(String)
    committed_date = Column(DateTime(timezone=True))
    repository_id = Column(Integer, ForeignKey("repositories.id"))

    @classmethod
    def from_github_data(cls, data: dict, repository_id: int):
        commit = data["commit"]
        return cls(
            github_sha=data["sha"],
            message=commit["message"],
            author_name=commit["author"]["name"],
            author_email=commit["author"]["email"],
            authored_date=datetime.fromisoformat(commit["author"]["date"].rstrip('Z')).replace(tzinfo=timezone.utc),
            committer_name=commit["committer"]["name"],
            committer_email=commit["committer"]["email"],
            committed_date=datetime.fromisoformat(commit["committer"]["date"].rstrip('Z')).replace(tzinfo=timezone.utc),
            repository_id=repository_id
        )

class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    number = Column(Integer)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    title = Column(String)
    state = Column(String)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True), nullable=True)
    author_login = Column(String)
    labels = Column(String)

    @classmethod
    def from_github_data(cls, data: dict, repository_id: int):
        closed_at = data.get("closed_at")
        return cls(
            number=data["number"],
            repository_id=repository_id,
            title=data["title"],
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            closed_at=datetime.fromisoformat(closed_at.rstrip('Z')).replace(tzinfo=timezone.utc) if closed_at else None,
            author_login=data["user"]["login"],
            labels=",".join(label["name"] for label in data["labels"])
        )

class IssueComment(Base):
    __tablename__ = "issue_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(BigInteger, ForeignKey("issues.id"))
    body = Column(String)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    author_login = Column(String)

    @classmethod
    def from_github_data(cls, data: dict, issue_id: int):
        return cls(
            issue_id=issue_id,
            body=data["body"],
            created_at=datetime.fromisoformat(data["created_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            author_login=data["user"]["login"]
        )

class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    number = Column(Integer)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    title = Column(String)
    state = Column(String)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True), nullable=True)
    merged_at = Column(DateTime(timezone=True), nullable=True)
    author_login = Column(String)
    base_branch = Column(String)
    head_branch = Column(String)
    is_merged = Column(Boolean)

    @classmethod
    def from_github_data(cls, data: dict, repository_id: int):
        closed_at = data.get("closed_at")
        merged_at = data.get("merged_at")
        return cls(
            number=data["number"],
            repository_id=repository_id,
            title=data["title"],
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            closed_at=datetime.fromisoformat(closed_at.rstrip('Z')).replace(tzinfo=timezone.utc) if closed_at else None,
            merged_at=datetime.fromisoformat(merged_at.rstrip('Z')).replace(tzinfo=timezone.utc) if merged_at else None,
            author_login=data["user"]["login"],
            base_branch=data["base"]["ref"],
            head_branch=data["head"]["ref"],
            is_merged=data.get("merged", False)
        )

class PullRequestComment(Base):
    __tablename__ = "pull_request_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"))
    body = Column(String)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    author_login = Column(String)
    is_initial = Column(Boolean, default=False)  # True for the PR description/body

    @classmethod
    def from_github_data(cls, data: dict, pull_request_id: int, is_initial: bool = False):
        if is_initial:
            return cls(
                pull_request_id=pull_request_id,
                body=data.get("body", ""),
                created_at=datetime.fromisoformat(data["created_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
                updated_at=datetime.fromisoformat(data["updated_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
                author_login=data["user"]["login"],
                is_initial=True
            )
        return cls(
            pull_request_id=pull_request_id,
            body=data["body"],
            created_at=datetime.fromisoformat(data["created_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            author_login=data["user"]["login"],
            is_initial=False
        )
