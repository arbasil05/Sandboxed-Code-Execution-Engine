from redis import Redis
from rq import SimpleWorker

redis_conn = Redis(host="localhost",port=6379)


if __name__ == "__main__":
    worker = SimpleWorker(queues=["submission_queue"],connection=redis_conn)
    print("Worker started")
    worker.work()