from pydantic import BaseModel
from typing import Any, Optional

class CodeSubmission(BaseModel):
    language: str
    code: str
    user_input: str = ""  # Optional: For scripts that require stdin

class SubmissionResponse(BaseModel):
    message: str
    job_id: str
    status: str

class ResultResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Any] = None