from schema import ResultResponse
from schema import CodeSubmission
from schema import SubmissionResponse
from fastapi import FastAPI, HTTPException
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from tasks import execute_code

app = FastAPI(title="Multi-Language Code Runner")

redis_conn = Redis(host="localhost", port=6379)
task_queue = Queue("submission_queue", connection=redis_conn)

@app.post("/submit", response_model=SubmissionResponse)
async def submit_code(submission: CodeSubmission):
    """
    Takes code, enqueues it for a background worker, and returns a tracking ID.
    """
    valid_languages = ["python", "javascript", "cpp"]
    if submission.language.lower() not in valid_languages:
        raise HTTPException(status_code=400, detail="Unsupported language")

    job = task_queue.enqueue(
        execute_code,
        submission.code,
        submission.language,
        submission.user_input,
        job_timeout=10
    )

    return SubmissionResponse(
        message="Code submitted successfully",
        job_id=job.id,
        status="queued"
    )

@app.get("/poll/{job_id}", response_model=ResultResponse)
async def poll_result(job_id: str):
    """
    Checks the status of a specific job and returns the output if finished.
    """
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job ID not found or expired.")

    if job.is_finished:
        return ResultResponse(
            job_id=job_id,
            status="completed",
            result=job.result
        )
    elif job.is_failed:
        return ResultResponse(
            job_id=job_id,
            status="failed",
            result={"error": "The background worker crashed while processing this job."}
        )
    else:
        raw_status = job.get_status()
        status_str = str(raw_status).split(".")[-1].lower()
        return ResultResponse(
            job_id=job_id,
            status=status_str,
            result=None
        )
