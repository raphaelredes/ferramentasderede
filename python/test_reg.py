import winreg
import subprocess

def debug_reg():
    paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\WSMAN",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\WSMAN\Client",
        r"SOFTWARE\Policies\Microsoft\Windows\WinRM\Client"
    ]
    
    for path in paths:
        print(f"Checking {path}...")
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                print(f"  Opened successfully.")
                try:
                    i = 0
                    while True:
                        name, value, type_ = winreg.EnumValue(key, i)
                        print(f"    Value: {name} = {value}")
                        i += 1
                except OSError:
                    pass
        except FileNotFoundError:
            print(f"  Not found.")
        except Exception as e:
            print(f"  Error: {e}")

    print("\nChecking via PowerShell:")
    try:
        cmd = ["powershell", "-Command", "(Get-Item WSMan:\\localhost\\Client\\TrustedHosts).Value"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"  PowerShell Result: '{result.stdout.strip()}'")
    except Exception as e:
        print(f"  PowerShell Error: {e}")

if __name__ == "__main__":
    debug_reg()
