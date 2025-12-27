import subprocess

def is_ip_reachable(ip):
    command = ["ping", "-c", "1", ip, "-W", "1"]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False


while 1:
  # Example usage
  ip_address = "192.168.252.2"
  if is_ip_reachable(ip_address):
    print(f"{ip_address} is reachable.")
    break
  else:
    print(f"{ip_address} is not reachable.")
