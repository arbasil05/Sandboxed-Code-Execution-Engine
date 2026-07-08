import time
import docker
import redis
from pool_manager import provision_new_container,IDLE_POOL_KEY,BUSY_POOL_KEY

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
docker_client = docker.from_env()

TARGET_BUFFER = 5
MAX_POOL_SIZE = 50
CHECK_INTERVAL = 2

def get_pool_metrics():

    idle_count = redis_client.scard(IDLE_POOL_KEY)
    busy_count = redis_client.scard(BUSY_POOL_KEY)
    return idle_count,busy_count

def scale_up_pool(idle_count,total_containers):

    if idle_count < TARGET_BUFFER:
        
        needed = TARGET_BUFFER - idle_count

        available_slots = MAX_POOL_SIZE - total_containers
        to_spawn = min(needed,available_slots)

        if to_spawn > 0:
            print(f"[Daemon] Pool low! Idle: {idle_count}/{TARGET_BUFFER}. Scaling up by {to_spawn}...")
            for _ in range(to_spawn):
                try:
                    provision_new_container()
                except Exception as e:
                    print(f"[Daemon] Failed to provision container: {e}")
                    break # Stop trying if Docker daemon is struggling

def scale_down_pool(idle_count, busy_count):

    # When fully idle: enforce exactly TARGET_BUFFER containers
    # When jobs are running: allow a cushion to avoid over-reaping
    target = TARGET_BUFFER if busy_count == 0 else TARGET_BUFFER + 5

    if idle_count > target:
        excess = idle_count - target
        print(f"[Daemon] {'Idle-only trim' if busy_count == 0 else 'Pool saturated'}. Idle: {idle_count} → {target}. Reaping {excess} containers...")

        for _ in range(excess):

            container_id = redis_client.spop(IDLE_POOL_KEY)
            if not container_id:
                break

            try:
                container = docker_client.containers.get(container_id)
                container.kill()
                print(f"[Daemon] Successfully reaped container: {container_id}")
            except docker.errors.NotFound:
                pass
            except Exception as e:
                print(f"[Daemon] Error tearing down container {container_id}: {e}")

def reconcile_orphans():
    """On startup, kill any runner_ containers that Docker knows about but Redis doesn't."""
    known_ids = redis_client.smembers(IDLE_POOL_KEY) | redis_client.smembers(BUSY_POOL_KEY)
    all_runner_containers = docker_client.containers.list(filters={"name": "runner_"})

    orphans = [c for c in all_runner_containers if c.name not in known_ids]

    if orphans:
        print(f"[Daemon] Found {len(orphans)} orphaned container(s) not in Redis. Reaping...")
        for c in orphans:
            try:
                c.kill()
                print(f"[Daemon] Reaped orphan: {c.name}")
            except Exception as e:
                print(f"[Daemon] Failed to reap orphan {c.name}: {e}")
    else:
        print("[Daemon] No orphaned containers found.")

def run_daemon():
    print(f"[Daemon] Preemptive scaling daemon started. Target Buffer: {TARGET_BUFFER}, Max Capacity: {MAX_POOL_SIZE}")

    reconcile_orphans()

    while True:
        try:
            idle_count, busy_count = get_pool_metrics()
            total_containers = idle_count + busy_count
            
            # Check Scale Up Condition
            scale_up_pool(idle_count, total_containers)

            # Check Scale Down Condition
            scale_down_pool(idle_count, busy_count)
            
        except Exception as e:
            print(f"[Daemon] Loop error: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run_daemon()




