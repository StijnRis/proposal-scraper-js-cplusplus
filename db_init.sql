-- 1. Project Table
CREATE TABLE Project (
    project_id INTEGER PRIMARY KEY,
    -- Automatically auto-increments
    project_name TEXT NOT NULL,
    enhancement_proposal_name TEXT NOT NULL,
    copyright TEXT NOT NULL
);

-- 2. Person & Organisation
CREATE TABLE Person (
    person_id INTEGER PRIMARY KEY,
    full_name TEXT
);
CREATE TABLE Organisation (
    organisation_id INTEGER PRIMARY KEY,
    organisation_name TEXT NOT NULL
);
CREATE TABLE PersonUsername (
    person_id INTEGER NOT NULL,
    domain TEXT,
    username TEXT,
    real_name TEXT,
    PRIMARY KEY (person_id, domain, username),
    FOREIGN KEY (person_id) REFERENCES Person(person_id)
);
CREATE TABLE Affiliation (
    organisation_id INTEGER,
    person_id INTEGER,
    PRIMARY KEY (organisation_id, person_id),
    FOREIGN KEY (organisation_id) REFERENCES Organisation(organisation_id),
    FOREIGN KEY (person_id) REFERENCES Person(person_id)
);

-- 3. Proposal Table
CREATE TABLE Proposal (
    project_id INTEGER,
    proposal_id TEXT,
    proposer_id INTEGER,
    topic TEXT,
    proposal_type TEXT,
    PRIMARY KEY (project_id, proposal_id),
    FOREIGN KEY (project_id) REFERENCES Project(project_id),
    FOREIGN KEY (proposer_id) REFERENCES Person(person_id)
);

-- 4. Revisions & Authorship
CREATE TABLE ProposalRevision (
    project_id INTEGER,
    proposal_id TEXT,
    revision_index INTEGER,
    title TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    content TEXT,
    implemented_at_version TEXT,
    PRIMARY KEY (project_id, proposal_id, revision_index),
    FOREIGN KEY (project_id, proposal_id) REFERENCES Proposal(project_id, proposal_id)
);
CREATE TABLE StageHistory (
    project_id INTEGER,
    proposal_id TEXT,
    stage_index INTEGER,
    -- ENUM does not exist in SQLite, so we use CHECK constraint
    status TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (project_id, proposal_id, stage_index ),
    FOREIGN KEY (project_id, proposal_id) REFERENCES Proposal(project_id, proposal_id)
);
CREATE TABLE ProposalRevisionAuthor (
    project_id INTEGER,
    proposal_id TEXT,
    revision_index INTEGER,
    author_id INTEGER,
    PRIMARY KEY (
        project_id,
        proposal_id,
        revision_index,
        author_id
    ),
    FOREIGN KEY (author_id) REFERENCES Person(person_id),
    FOREIGN KEY (project_id, proposal_id, revision_index) REFERENCES ProposalRevision(project_id, proposal_id, revision_index)
);

-- 5. Relationships & Interactions
CREATE TABLE RelatedProposal (
    project_id INTEGER,
    proposal_id TEXT,
    related_project_id INTEGER,
    related_proposal_id TEXT,
    PRIMARY KEY (
        project_id,
        proposal_id,
        related_project_id,
        related_proposal_id
    ),
    FOREIGN KEY (project_id, proposal_id) REFERENCES Proposal(project_id, proposal_id),
    FOREIGN KEY (related_project_id, related_proposal_id) REFERENCES Proposal(project_id, proposal_id)
);
CREATE TABLE Comment (
    comment_id INTEGER PRIMARY KEY,
    author_id INTEGER,
    project_id INTEGER,
    proposal_id TEXT,
    comment_on_comment_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    content TEXT NOT NULL,
    FOREIGN KEY (author_id) REFERENCES Person(person_id),
    FOREIGN KEY (comment_on_comment_id) REFERENCES Comment(comment_id),
    FOREIGN KEY (project_id, proposal_id) REFERENCES Proposal(project_id, proposal_id)
);
