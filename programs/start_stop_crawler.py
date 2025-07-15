import argparse
import paramiko

SSH_USER = "ubuntu"
HOST_KEY_MAP = {
    "IP": "KEY",
    "IP": "KEY",
    "IP": "KEY",
}

def control_service(host, command):
    key_path = HOST_KEY_MAP[host]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=SSH_USER, key_filename=key_path)
    stdin, stdout, stderr = client.exec_command(f"sudo systemctl {command} crawler.service")
    exit_code = stdout.channel.recv_exit_status()
    client.close()
    return exit_code, stdout.read().decode(), stderr.read().decode()

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--on", action="store_true")
    group.add_argument("--off", action="store_true")
    args = parser.parse_args()
    command = "start" if args.on else "stop"
    for host in HOST_KEY_MAP:
        print(f"{'Starting' if args.on else 'Stopping'} crawler.service on {host}")
        code, out, err = control_service(host, command)
        if code == 0:
            print("Success")
        else:
            print(f"Failed (exit {code})\n{err.strip()}")

if __name__ == "__main__":
    main()
