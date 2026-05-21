import datetime

from pydantic import BaseModel


class StageEvent(BaseModel):
    proposal_id: str
    created_at: datetime.datetime
    stage: str


class ProposalRevision(BaseModel):
    proposal_id: str
    title: str
    created_at: datetime.datetime
    content: str
    authors: set[str]


class Proposal(BaseModel):
    proposal_id: str
    stages: list[StageEvent]
    subgroup: str
    revisions: list[ProposalRevision]


class Comment(BaseModel):
    proposal_id: str | None
    message_id: int
    url: str
    reply_to_message_id: int | None = None
    author_name: str
    source_domain: str
    author_email: str
    date: datetime.datetime
    content: str
