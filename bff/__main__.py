import sys
import uvicorn
import asyncio
from bff.config import config
from bff.process import manager

async def _check_port_async(port):
    try:
        server = await asyncio.start_server(lambda r,w: None, "127.0.0.1", port)
        server.close()
        await server.wait_closed()
        return True
    except OSError:
        return False

def check_port(port):
    return asyncio.run(_check_port_async(port))

def main():
    if not check_port(config["bff_port"]):
        print(f"Error: Port {config['bff_port']} is already in use.")
        sys.exit(2)
        
    try:
        manager.start("flood")
    except Exception as e:
        print(f"Failed to start MCP server: {e}")
        sys.exit(1)
        
    print(f"R.I.S.E. web: http://127.0.0.1:{config['bff_port']}")
    print("MCP server: running (token not shown)")
    print("Demo mode: simulated clock on")
    
    # Configure uvicorn to disable header logging by customizing the log config if needed.
    # By default Uvicorn access log doesn't log headers, but to be sure we can set format.
    log_config = uvicorn.config.LOGGING_CONFIG.copy()
    
    try:
        uvicorn.run(
            "bff.app:app",
            host="127.0.0.1",
            port=config["bff_port"],
            log_config=log_config,
            access_log=True
        )
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()

if __name__ == "__main__":
    main()
