import re
import subprocess
import os

def test_regex():
    output = "Disparando adm-42864.betim.pmb [10.10.90.199] com 32 bytes de dados"
    match = re.search(r"(?:Disparando|Pinging)(?:\s+contra)?\s+(.*?)\s+\[", output, re.IGNORECASE)
    if match:
        print(f"Regex Match: '{match.group(1)}'")
    else:
        print("Regex Failed")

def test_ping_a(ip):
    print(f"Testing ping -a for {ip}...")
    try:
        cmd = ["ping", "-a", "-n", "1", "-w", "1500", ip]
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='cp850', 
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        print("Output:")
        print(result.stdout)
        
        match = re.search(r"(?:Disparando|Pinging)(?:\s+contra)?\s+(.*?)\s+\[", result.stdout, re.IGNORECASE)
        if match:
            print(f"Parsed Hostname: '{match.group(1)}'")
        else:
            print("Failed to parse hostname")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("--- Regex Test ---")
    test_regex()
    print("\n--- Live Test ---")
    # Tentar com o IP da imagem se acessível, ou localhost
    test_ping_a("127.0.0.1")
    test_ping_a("8.8.8.8")
