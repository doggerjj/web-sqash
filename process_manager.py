#!/usr/bin/env python3
import argparse
import subprocess
import os
import sys
import json
from datetime import datetime

class ProcessManager:
    def __init__(self):
        self.processes_file = os.path.expanduser("~/.process_manager.json")
        self.processes = self._load_processes()

    def _load_processes(self):
        if os.path.exists(self.processes_file):
            try:
                with open(self.processes_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_processes(self):
        with open(self.processes_file, 'w') as f:
            json.dump(self.processes, f, indent=2)

    def start(self, name, command, output_file=None):
        if name in self.processes:
            print(f"Process '{name}' already exists!")
            return

        if output_file is None:
            output_file = f"{name}_output.log"

        full_command = f"nohup {command} > {output_file} 2>&1 &"
        process = subprocess.Popen(full_command, shell=True)
        
        # Wait briefly to get the actual background PID
        subprocess.run("sleep 1", shell=True)
        try:
            pid = int(subprocess.check_output(f"pgrep -f '{command}'", shell=True).decode().strip())
            
            self.processes[name] = {
                "pid": pid,
                "command": command,
                "output_file": output_file,
                "started_at": datetime.now().isoformat()
            }
            self._save_processes()
            print(f"Started process '{name}' with PID {pid}")
        except:
            print("Failed to get process PID. Process may not have started correctly.")

    def stop(self, name):
        if name not in self.processes:
            print(f"Process '{name}' not found!")
            return

        pid = self.processes[name]["pid"]
        try:
            subprocess.run(f"kill {pid}", shell=True)
            print(f"Stopped process '{name}' (PID: {pid})")
            del self.processes[name]
            self._save_processes()
        except:
            print(f"Failed to stop process '{name}'")

    def list(self):
        if not self.processes:
            print("No active processes")
            return

        print("\nActive Processes:")
        print("-" * 80)
        for name, info in self.processes.items():
            print(f"Name: {name}")
            print(f"PID: {info['pid']}")
            print(f"Command: {info['command']}")
            print(f"Output File: {info['output_file']}")
            print(f"Started At: {info['started_at']}")
            print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description="Process Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start a new process")
    start_parser.add_argument("name", help="Name for the process")
    start_parser.add_argument("command", help="Command to run")
    start_parser.add_argument("--output", help="Output file (default: name_output.log)")

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop a process")
    stop_parser.add_argument("name", help="Name of the process to stop")

    # List command
    subparsers.add_parser("list", help="List all processes")

    args = parser.parse_args()
    pm = ProcessManager()

    if args.command == "start":
        pm.start(args.name, args.command, args.output)
    elif args.command == "stop":
        pm.stop(args.name)
    elif args.command == "list":
        pm.list()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()