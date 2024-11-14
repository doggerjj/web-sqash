# Erendil

Save this script as `process_manager.py` and make it executable:

```bash
chmod +x process_manager.py
```

Here's how to use it:

1. Start a new process:

```bash
./process_manager.py start myapp "uv run python fastapi_app.py"
```

2. List all running processes:

```bash
./process_manager.py list
```

3. Stop a process:

```bash
./process_manager.py stop myapp
```

The script features:

- Keeps track of running processes in a JSON file (`~/.process_manager.json`)
- Manages output logs automatically
- Stores process information including PID, command, start time
- Easy to use CLI interface
- Persists process information across SSH sessions

You can also create an alias in your `.bashrc` or .`zshrc`:

```bash
alias pm='path/to/process_manager.py'
```

Then use it like:

```bash
pm start myapp "uv run python fastapi_app.py"
pm list
pm stop myapp
```

The script stores all process information in `~/.process_manager.json`, so you can track and manage your processes even after logging out and back in.