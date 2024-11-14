# Erendil

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