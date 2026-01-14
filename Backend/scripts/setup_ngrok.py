import os
import platform
import subprocess
import sys
from pathlib import Path
import ctypes

NGROK_AUTH_TOKEN = "2sH4UpyyPibfSTGSQcdRQl0Bznt_4KG2jD7nh22kEacyaAhde"
STATIC_DOMAIN = "moth-uncommon-minnow.ngrok-free.app"
PORT = "5000"


def is_admin():
    try:
        if platform.system() == "Windows":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        else:
            return os.getuid() == 0
    except:
        return False


def elevate_privileges():
    if platform.system() == "Windows":
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()
    else:
        if sys.executable and os.path.exists(sys.executable):
            args = ['sudo', sys.executable] + sys.argv
            os.execvp('sudo', args)
        else:
            print("Error: Could not determine Python executable path")
            sys.exit(1)


def run_command(command, shell=True):
    try:
        result = subprocess.run(
            command,
            shell=shell,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return False


def is_command_exists(command):
    try:
        subprocess.run(
            [command, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True
    except FileNotFoundError:
        return False


def setup_ngrok_config(config_dir):
    config_content = f"""
version: "3"
agent:
    authtoken: {NGROK_AUTH_TOKEN}
endpoints:
    - name: custom-domain
    description: "Custom static domain for my application
    url: {STATIC_DOMAIN}
    upstream:
        url: http://localhost:{PORT}        
"""
    # Create config directory if it doesn't exist
    os.makedirs(config_dir, exist_ok=True)

    # Write configuration file
    config_path = os.path.join(config_dir, "ngrok.yml")
    with open(config_path, 'w') as f:
        f.write(config_content)

    print(f"ngrok configuration has been created at: {config_path}")


def setup_windows():
    if not is_admin():
        print("This script need to be run as Administrator on Windows")
        sys.exit(1)

    # Check and install Chocolatey
    if not is_command_exists('choco'):
        print("Installing Chocolatey...")
        choco_install_cmd = """Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"""
        powershell_cmd = f'powershell -Command "{choco_install_cmd}"'
        if not run_command(powershell_cmd):
            print("Failed to install Chocolatey. Please install it manually")
            sys.exit(1)

    # Install ngrok using Chocolatey
    if not is_command_exists('ngrok'):
        print("Installing ngrok...")
        if not run_command('choco install ngrok -y'):
            print("Failed to install ngrok. Please install it manually")
            sys.exit(1)

    # Setup configuration
    config_dir = os.path.join(os.environ['LOCALAPPDATA'], 'ngrok')
    setup_ngrok_config(config_dir)

def setup_linux():
    if not is_command_exists('ngrok'):
        print('Installing ngrok...')
        commands = [
            'curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null',
            'echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list',
            'sudo apt update',
            'sudo apt install -y ngrok'
        ]
        for cmd in commands:
            if not run_command(cmd):
                print(f"Failed to execute: {cmd}")
                print("Please install ngrok manually")
                sys.exit(1)

    config_dir = os.path.join(str(Path.home()), '.ngrok2')
    setup_ngrok_config(config_dir)

def setup_macos():
    if not is_command_exists('ngrok'):
        print("Installing ngrok")
        if not is_command_exists('brew'):
            print('Homebrew is required but not installed')
            print('Please install Homebrew first: https://brew.sh')
            sys.exit(1)

        if not run_command('brew install ngrok'):
            print("Failed to install ngrok. Please install it manually")
            sys.exit(1)

    config_dir = os.path.join(str(Path.home()), 'Library/Application Support/ngrok')
    setup_ngrok_config(config_dir)

def main():
    # Check for admin rights and elevate if needed
    if not is_admin():
        print("Requesting administrative privileges...")
        elevate_privileges()
        print("Failed to obtain administrative privileges")
        sys.exit(1)

    system = platform.system().lower()
    print(f"Detected operating system: {system}")

    try:
        if system == 'windows':
            setup_windows()
        elif system == 'linux':
            setup_linux()
        elif system == 'darwin':
            setup_macos()
        else:
            print(f"Unsupported operating system: {system}")
            sys.exit(1)

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()