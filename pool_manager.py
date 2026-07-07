import uuid
import docker
from redis import Redis
import time
import random

redis_client = Redis(host="localhost",port=6379,decode_responses=True)
docker_client = docker.from_env()

IDLE_POOL_KEY = "pool:idle"
BUSY_POOL_KEY = "pool:busy"
IMAGE_NAME = "python:3.10-slim"

def provision_new_container():

    container_id = f"runner_{uuid.uuid4().hex[:8]}"

    container = docker_client.containers.run(
        image=IMAGE_NAME,
        # this command will keep the container running forever
        command=["sh", "-c", "tail -f /dev/null"], #starts a shell inside the container,-c : execute the following command, tail : eof ,-f : keep the file forever and /dev/null : accepts anything written to it and never stores anything
        name=container_id,
        detach=True,
        remove=True,
        network_disabled=True,
        mem_limit="128m",
        pids_limit=50,
        read_only=True,
        tmpfs={'/tmp':''}
    )

    redis_client.sadd(IDLE_POOL_KEY, container_id)
    print(f"[Pool] Provisioned and registered warm container: {container_id}")
    return container_id

def acquire_container(timeout_seconds=10):
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:

        container_id = redis_client.srandmember(IDLE_POOL_KEY)
        
        if container_id:
            success = redis_client.smove(IDLE_POOL_KEY, BUSY_POOL_KEY, container_id)
            if success:
                return container_id
        
        time.sleep(random.uniform(0.05, 0.2))
    raise TimeoutError("Timeout: No warm containers became available in time.")

def release_container(container_id):
    redis_client.smove(BUSY_POOL_KEY,IDLE_POOL_KEY,container_id)
    print(f"[Pool] Container {container_id} returned to idle pool.")
