import re
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Column, Text
from backend.models.base import Base


def _get_pr_number_from_title(title: str) -> int:
    """Extracts the pull request number from a commit title. Like (#142) and (gh-142)"""
    pattern1 = r'\(#(\d+)\)'
    match = re.search(pattern1, title)
    if match:
        return int(match.group(1))
    
    # Match (gh-number) format, case insensitive
    pattern2 = r'\((?i:gh)-(\d+)\)'
    match = re.search(pattern2, title)
    if match:
        return int(match.group(1))
    
    return None


class RepositoryLanguage(Base):
    __tablename__ = "repository_languages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    language = Column(String, nullable=False)
    bytes_count = Column(Integer, nullable=False)


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
    readme_content = Column(Text, nullable=True)
    readme_path = Column(String, nullable=True)

    @classmethod
    def from_github_data(cls, data: dict):
        owner, name = data["full_name"].split("/")
        return cls(
            owner=owner,
            name=name,
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            default_branch=data["default_branch"],
            stars_count=data["stargazers_count"],
            forks_count=data["forks_count"],
            is_initialized=False,
            readme_content=None,
            readme_path=None
        )

class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    github_sha = Column(String, unique=True)
    parent_sha = Column(String, nullable=True)
    message = Column(String)
    author_name = Column(String)
    author_email = Column(String)
    authored_date = Column(DateTime(timezone=True))
    committer_name = Column(String)
    committer_email = Column(String)
    committed_date = Column(DateTime(timezone=True))
    pull_request_number = Column(Integer, nullable=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"))

    @classmethod
    def from_github_data(cls, data: dict, repository_id: int, set_null_parent: bool = False):
        commit = data["commit"]
        parent_sha = None if set_null_parent else (data["parents"][0]["sha"] if data.get("parents") else None)
        return cls(
            github_sha=data["sha"],
            parent_sha=parent_sha,
            message=commit["message"],
            author_name=commit["author"]["name"],
            author_email=commit["author"]["email"],
            authored_date=datetime.fromisoformat(commit["author"]["date"].rstrip('Z')).replace(tzinfo=timezone.utc),
            committer_name=commit["committer"]["name"],
            committer_email=commit["committer"]["email"],
            committed_date=datetime.fromisoformat(commit["committer"]["date"].rstrip('Z')).replace(tzinfo=timezone.utc),
            repository_id=repository_id,
            pull_request_number=_get_pr_number_from_title(commit["message"]),
        )

class CommitSummary(Base):
    __tablename__ = "commit_summaries"

    id = Column(Integer, primary_key=True)
    commit_id = Column(Integer, ForeignKey("commits.id"), unique=True)
    summary = Column(Text, nullable=False)

class CommitDiff(Base):
    __tablename__ = "commit_diffs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String, nullable=False)
    diff_content = Column(Text)
    
    # Foreign key relationships
    commit_id = Column(Integer, ForeignKey("commits.id"))

    @classmethod
    def from_github_data(cls, commit_id: int, file_diff: dict):
        return cls(
            commit_id=commit_id,
            file_path=file_diff["filename"],
            diff_content=file_diff.get("patch"),
        )

class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    number = Column(Integer)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    title = Column(String)
    body = Column(String, nullable=True)
    state = Column(String)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True), nullable=True)
    author_login = Column(String)
    labels = Column(String)
    is_pull_request = Column(Boolean, default=False)

    @classmethod
    def from_github_data(cls, data: dict, repository_id: int):
        closed_at = data.get("closed_at")
        return cls(
            number=data["number"],
            repository_id=repository_id,
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip('Z')).replace(tzinfo=timezone.utc),
            closed_at=datetime.fromisoformat(closed_at.rstrip('Z')).replace(tzinfo=timezone.utc) if closed_at else None,
            author_login=data["user"]["login"],
            labels=",".join(label["name"] for label in data["labels"]),
            is_pull_request="pull_request" in data,
        )
    
class DeletedIssue(Base):
    __tablename__ = "deleted_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    number = Column(Integer)
    repository_id = Column(Integer, ForeignKey("repositories.id"))

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

class ReadmeSummary(Base):
    __tablename__ = "readme_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), unique=True)
    summarization = Column(Text)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PullRequestSummary(Base):
    __tablename__ = "pull_request_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), unique=True)
    summarization = Column(Text)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


if __name__ == "__main__":
    print(_get_pr_number_from_title("mrg (#1) from test/branch"))
    print(_get_pr_number_from_title("Merge (gh-2) from test/branch"))
    print(_get_pr_number_from_title("GH-5123 fix"))
    print(_get_pr_number_from_title("fix (#5123)"))
    print(_get_pr_number_from_title("fix #512 (GH-515)"))
    print(_get_pr_number_from_title("gh-512 fix (#515)"))
    print(_get_pr_number_from_title("(gh-12412): fix"))