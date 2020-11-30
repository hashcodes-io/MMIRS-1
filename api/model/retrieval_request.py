from typing import Optional

from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query: str = Field(description="Query to the image retrieval model. E.g. 'Two girls eating icecream.'")
    difficult_word: Optional[str] = None
    top_k: Optional[int] = 3
