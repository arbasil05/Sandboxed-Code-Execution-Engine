import docker
import time
from pool_manager import acquire_container, release_container

client = docker.from_env()

# Expanded Language Map for a General Runner
LANGUAGE_MAP = {
    "python": {
        "filename": "solution.py",
        "run_command": "python /tmp/solution.py"
    },
    "javascript": {
        "filename": "solution.js",
        "run_command": "node /tmp/solution.js"
    },
    "cpp": {
        "filename": "solution.cpp",
        # Compiles to an executable, then runs it. 
        # If compilation fails, the error goes to stderr.
        "run_command": "g++ /tmp/solution.cpp -o /tmp/solution && /tmp/solution"
    }
}

def execute_code(code_string, language, user_input=""):
    """
    Executes arbitrary code in a sandboxed, pre-warmed container.
    Accepts optional stdin via `user_input`.
    """
    lang_config = LANGUAGE_MAP.get(language.lower())
    if not lang_config:
        return {"status": "error", "error_message": f"Unsupported language: {language}"}

    # 1. Grab a warm container
    try:
        container_id = acquire_container(timeout_seconds=10)
    except TimeoutError as e:
        return {"status": "error", "error_message": "System overloaded, no runners available."}

    try:
        container = client.containers.get(container_id)
        
        filename = lang_config["filename"]
        run_cmd = lang_config["run_command"]

        # Pass both the code and any standard input the user provided
        env_vars = {
            "USER_CODE": code_string,
            "USER_INPUT": user_input
        }

        # Write code to file, pipe user_input to the execution command, enforce a 5s timeout
        shell_command = f"sh -c 'printenv USER_CODE > /tmp/{filename} && printenv USER_INPUT | timeout 5 {run_cmd}'"

        # 2. Execute with demux=True to separate stdout and stderr
        exit_code, output_streams = container.exec_run(
            cmd=shell_command,
            environment=env_vars,
            workdir="/tmp",
            user="root", 
            demux=True  # <--- THIS IS THE MAGIC KEY
        )

        # Output streams is a tuple of (stdout_bytes, stderr_bytes)
        # Docker SDK returns None if a stream is empty, so we default to b""
        raw_stdout = output_streams[0] or b""
        raw_stderr = output_streams[1] or b""

        stdout = raw_stdout.decode("utf-8")
        stderr = raw_stderr.decode("utf-8")

        # 3. Determine the final status
        if exit_code == 124:
            status = "timeout"
            stderr = "Error: Code execution timed out after 5 seconds."
        elif exit_code != 0:
            status = "runtime_error"
        else:
            status = "success"

        # 4. Clean up /tmp so the container is fresh for the next user
        container.exec_run("sh -c 'rm -rf /tmp/*'")

        return {
            "status": status,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code
        }

    except Exception as e:
        return {"status": "error", "error_message": f"Execution engine failure: {str(e)}"}

    finally:
        # 5. Always put the toy back in the box
        release_container(container_id)