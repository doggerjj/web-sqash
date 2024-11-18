import argparse
import subprocess
import os
import signal
import sys
from typing import Optional
import psutil  # You'll need to install this: pip install psutil

class ProcessManager:
    def __init__(self):
        self.process_file = "running_processes.txt"

    def start_process(self, log_file: str) -> None:
        """Start a new process and save its PID"""
        try:
            # Start the process using nohup
            process = subprocess.Popen(
                f"nohup uv run python main.py > {log_file} 2>&1",
                shell=True,
                preexec_fn=os.setpgrp
            )
            
            # Wait briefly to let child processes spawn
            subprocess.run("sleep 1", shell=True)
            
            # Get all related processes
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            
            # Save all PIDs and log file information
            with open(self.process_file, "a") as f:
                f.write(f"{process.pid},{','.join(str(child.pid) for child in children)},{log_file}\n")
            
            print(f"Started process group with main PID {process.pid}, logging to {log_file}")
        
        except Exception as e:
            print(f"Error starting process: {e}")

    def stop_process(self, log_file: str) -> None:
        """Stop all processes associated with the given log file"""
        pids = self._find_pids_by_log(log_file)
        if pids:
            try:
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        print(f"Stopped process with PID {pid}")
                    except ProcessLookupError:
                        continue
                    except Exception as e:
                        print(f"Error stopping PID {pid}: {e}")
                self._remove_process_entry(log_file)
            except Exception as e:
                print(f"Error stopping processes: {e}")
        else:
            print(f"No running processes found for {log_file}")

    def list_processes(self) -> None:
        """List all running processes"""
        if not os.path.exists(self.process_file):
            print("No running processes")
            return

        print("\nRunning processes:")
        print("PIDs\t\t\tLog File")
        print("-" * 50)
        
        with open(self.process_file, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                log_file = parts[-1]
                pids = parts[:-1]
                
                running_pids = []
                for pid in pids:
                    if self._is_process_running(int(pid)):
                        running_pids.append(pid)
                
                if running_pids:
                    print(f"{', '.join(running_pids)}\t{log_file}")
                else:
                    self._remove_process_entry(log_file)
    
    def stop_all_processes(self) -> None:
        """Stop all managed processes"""
        if not os.path.exists(self.process_file):
            print("No running processes to stop")
            return

        with open(self.process_file, "r") as f:
            lines = f.readlines()

        if not lines:
            print("No running processes to stop")
            return

        stopped_count = 0
        for line in lines:
            parts = line.strip().split(",")
            pids = [int(pid) for pid in parts[:-1]]  # All PIDs except the last element (log file)
            log_file = parts[-1]

            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"Stopped process with PID {pid} (log: {log_file})")
                    stopped_count += 1
                except ProcessLookupError:
                    continue
                except Exception as e:
                    print(f"Error stopping PID {pid}: {e}")

        # Clear the process file
        os.remove(self.process_file)
        print(f"\nStopped {stopped_count} processes in total")

    def _find_pids_by_log(self, log_file: str) -> list[int]:
        """Find all PIDs for a given log file"""
        if not os.path.exists(self.process_file):
            return []

        with open(self.process_file, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                stored_log = parts[-1]
                if stored_log == log_file:
                    return [int(pid) for pid in parts[:-1]]
        return []

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running"""
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def _remove_process_entry(self, log_file: str) -> None:
        """Remove a process entry from the tracking file"""
        if not os.path.exists(self.process_file):
            return

        lines = []
        with open(self.process_file, "r") as f:
            lines = f.readlines()

        with open(self.process_file, "w") as f:
            for line in lines:
                if log_file not in line:
                    f.write(line)

def main():
    parser = argparse.ArgumentParser(description="Process Manager CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", help="Start a new process with specified log file")
    group.add_argument("--stop", help="Stop the process with specified log file")
    group.add_argument("--stop-all", action="store_true", help="Stop all running processes")
    group.add_argument("--list", action="store_true", help="List all running processes")

    args = parser.parse_args()
    pm = ProcessManager()

    if args.start:
        pm.start_process(args.start)
    elif args.stop:
        pm.stop_process(args.stop)
    elif args.stop_all:
        pm.stop_all_processes()
    elif args.list:
        pm.list_processes()

if __name__ == "__main__":
    main()