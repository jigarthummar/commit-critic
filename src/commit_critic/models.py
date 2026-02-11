from dataclasses import dataclass, field

@dataclass
class CommitInfo:
    hash: str
    author: str
    date: str
    message: str


@dataclass
class CommitCritique:
    hash: str
    message: str
    score: int
    issue: str = ""
    suggestion: str = ""
    praise: str = ""


@dataclass
class RepoStats:
    total: int = 0
    avg_score: float = 0.0
    vague_count: int = 0
    decent_count: int = 0
    one_word_count: int = 0
    good_count: int = 0
    critiques: list = field(default_factory=list)
