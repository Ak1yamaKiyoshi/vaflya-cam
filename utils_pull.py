import subprocess
import os
import sys
import time

with open("password.txt", "r+") as f:
    PASSWORD = f.read().strip()

REMOTE = "hex@hex.local"

REMOTE_PATH = "~/Desktop/gravicam/outputs/"
HOST_PATH = os.path.join(os.path.abspath("./"), "pull")
print(HOST_PATH)
print(REMOTE_PATH)

RSYNC_IGNORE_LIST = [".git", "__pycache__", ".pyc"]

def sync_code():
    mkdir_cmd = f"sshpass -p '{PASSWORD}' ssh {REMOTE} 'mkdir -p {REMOTE_PATH}'"
    try:
        subprocess.run(mkdir_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error creating remote directory: {e.stderr.decode()}")
        return False

    exclude_options = ' '.join([f"--exclude='*{pattern}*'" for pattern in RSYNC_IGNORE_LIST])
    rsync_cmd = f"sshpass -p '{PASSWORD}' rsync -avz {exclude_options} {REMOTE}:{REMOTE_PATH} {HOST_PATH}"

    try:
        result = subprocess.run(rsync_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Rsync error: {e.stderr.decode()}")
        return False

if __name__ == "__main__":
    try:
        subprocess.run(["which", "sshpass"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        print("Error: sshpass is not installed.")
        sys.exit(1)

    while True:
        success = sync_code()
        print(f"\r OK? {success}, {time.time()}", end="", flush=False)
        time.sleep(0.1)