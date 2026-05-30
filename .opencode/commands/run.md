Manage services using the CLI:

```bash
cli service start <service>      # launch in background
cli service stop <service>       # graceful shutdown (SIGTERM)
cli service restart <service>    # stop then start
cli service status               # show all services (PID, status, uptime)
cli service configure <service>  # view/edit .env config
cli service health <service>     # query health status
cli service logs <service>       # tail service logs
```

Each service entry point is `python <service-name>/main.py run`.
Configuration is loaded from the `.env` file in each service folder.
Activate the virtual environment first: `source cenv/bin/activate`