CREATE TABLE repositories (
    id INTEGER PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    default_branch VARCHAR(255),
    stars_count INTEGER DEFAULT 0,
    forks_count INTEGER DEFAULT 0,
    is_initialized BOOLEAN DEFAULT FALSE
);

CREATE TABLE commits (
    sha VARCHAR(40) PRIMARY KEY,
    message TEXT,
    author_name VARCHAR(255),
    author_email VARCHAR(255),
    authored_date TIMESTAMP WITH TIME ZONE,
    committer_name VARCHAR(255),
    committer_email VARCHAR(255),
    committed_date TIMESTAMP WITH TIME ZONE,
    repository_id INTEGER REFERENCES repositories(id)
);

CREATE TABLE issues (
    number INTEGER,
    repository_id INTEGER REFERENCES repositories(id),
    title VARCHAR(255),
    body TEXT,
    state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE,
    author_login VARCHAR(255),
    labels JSONB,
    PRIMARY KEY (repository_id, number)
);

CREATE TABLE pull_requests (
    number INTEGER,
    repository_id INTEGER REFERENCES repositories(id),
    title VARCHAR(255),
    body TEXT,
    state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE,
    merged_at TIMESTAMP WITH TIME ZONE,
    author_login VARCHAR(255),
    base_branch VARCHAR(255),
    head_branch VARCHAR(255),
    is_merged BOOLEAN,
    PRIMARY KEY (repository_id, number)
);
