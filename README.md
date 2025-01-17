# Erendil

## To run normally

1. Using `nohup` directly:

    ```bash
    nohup uv run python main.py > trader.log 2>&1 &
    ```

After running either command, you can:

- Check if it's running with:

    ```bash
    ps aux | grep main.py
    ```

- View the logs in real-time with:

    ```bash
    tail -f trader.log
    ```

- To stop it later, find its PID and kill it:

    ```bash
    ps aux | grep main.py 
    kill <PID> 
    ```


## To run with process.py

- To start a process
    ```bash
    python process.py --start <filename.log>
    ```

- To list running processes
    ```bash
    python process.py --list
    ```

- To stop active process
    ```bash
    python process.py --stop <filename.log>
    ```

- To stop all active processes
    ```bash
    python process.py --stop-all
    ```

## To see the process using the port <port> eg:8000

    ```bash
    lsof -i :8000
    ```

## To force kill a process:

    ```bash
    kill -9 <PID>
    ````