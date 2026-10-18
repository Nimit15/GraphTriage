"""
Central FalkorDB connection factory with cloud credentials support.

This module provides a centralized connection management system for FalkorDB
that handles environment variable loading, endpoint parsing, and intelligent
fallback behavior for both cloud and local deployments.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple, Any
from dotenv import load_dotenv
from falkordb import FalkorDB

logger = logging.getLogger(__name__)

# Load environment variables from project root .env file, unless disabled
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if os.getenv("PYTHON_DOTENV_DISABLED") != "1":
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)

def _parse_endpoint(host: str, port: Any) -> Tuple[str, int]:
    """Parse and normalize FalkorDB endpoint configuration.

    Args:
        host: FalkorDB host (may contain protocol or port)
        port: FalkorDB port

    Returns:
        Tuple of (host, port) with normalized values
    """
    # Handle protocol prefixes
    if host.startswith(("http://", "https://", "redis://", "rediss://")):
        # Strip protocol prefix if present
        for proto in ["http://", "https://", "redis://", "rediss://"]:
            if host.startswith(proto):
                host = host[len(proto):]
                break

    # Handle host:port format
    if ":" in host and not host.startswith("["):
        # Split host:port format
        parts = host.split(":")
        if len(parts) == 2:
            potential_port = parts[1]
            if potential_port.isdigit():
                host = parts[0]
                port = int(potential_port)

    return host, port

def _try_cloud_connection() -> Optional[FalkorDB]:
    """Try to connect to FalkorDB Cloud using credentials from .env.

    Returns:
        FalkorDB client if successful, None otherwise.
    """
    cloud_host = os.getenv("FALKORDB_HOST", "")

    # Check for cloud host patterns
    if "falkordb.cloud" not in cloud_host and ".instance" not in cloud_host:
        return None

    logger.info(f"Found FalkorDB Cloud credentials: host={cloud_host}, port={os.getenv('FALKORDB_PORT')}")

    conn_params = {
        "host": cloud_host,
        "port": int(os.getenv("FALKORDB_PORT", "57210")),
    }

    # Add authentication if available
    username = os.getenv("FALKORDB_USERNAME")
    password = os.getenv("FALKORDB_PASSWORD")
    if username and password:
        conn_params["username"] = username
        conn_params["password"] = password

    # Add SSL if configured
    ssl_env = os.getenv("FALKORDB_SSL", "false").lower()
    if ssl_env in ("true", "1", "yes"):
        conn_params["ssl"] = True

    try:
        client = FalkorDB(**conn_params)
        test_graph = client.select_graph("graphtriage_test")
        test_graph.query("RETURN 1 as test")
        logger.info(f"Successfully connected to FalkorDB cloud at {cloud_host}:{os.getenv('FALKORDB_PORT')}")
        return client
    except Exception as e:
        logger.error(f"FalkorDB Cloud connection failed: {e}")
        return None

def get_falkordb_client() -> FalkorDB:
    """Get a FalkorDB client with cloud credentials support and intelligent fallback.

    This function implements a smart connection strategy:
    1. First tries cloud credentials if detected
    2. Tries FALKORDB_URL for direct connection
    3. Falls back to FALKORDB_HOST/FALKORDB_PORT with intelligent parsing

    Returns:
        Configured FalkorDB client instance

    Raises:
        ConnectionError: If unable to connect after all fallback attempts
    """
    # Try cloud connection first if credentials are detected
    cloud_client = _try_cloud_connection()
    if cloud_client:
        return cloud_client

    # Try FALKORDB_URL first (direct connection string)
    falkordb_url = os.getenv("FALKORDB_URL")
    if falkordb_url:
        logger.info(f"Using FalkorDB URL")
        try:
            from urllib.parse import urlparse
            parsed = urlparse(falkordb_url)

            username = parsed.username or os.getenv("FALKORDB_USERNAME")
            password = parsed.password or os.getenv("FALKORDB_PASSWORD")
            host = parsed.hostname or os.getenv("FALKORDB_HOST", "localhost")
            port = parsed.port or int(os.getenv("FALKORDB_PORT", "6379"))
            ssl = parsed.scheme in ("rediss", "https", "wss")

            if username and password:
                client = FalkorDB.from_url(falkordb_url, username=username, password=password)
            else:
                client = FalkorDB.from_url(falkordb_url)

            logger.info("Successfully created FalkorDB client from URL")
            return client

        except Exception as e:
            logger.warning(f"Failed to create FalkorDB client from URL: {e}")
            logger.info("Falling back to host/port configuration")

    # Fallback to FALKORDB_HOST/FALKORDB_PORT configuration
    falkordb_host = os.getenv("FALKORDB_HOST", "localhost")

    # Check if PYTHON_DOTENV_DISABLED is set and if so, don't default to .env values
    if os.getenv("PYTHON_DOTENV_DISABLED") != "1":
        # Try to get port from environment, fall back to 6379 if not set
        falkordb_port = os.getenv("FALKORDB_PORT", "6379")
    else:
        # If .env is disabled, always use 6379 as the default
        falkordb_port = os.getenv("FALKORDB_PORT", "6379")

    # Parse and normalize endpoint
    try:
        host, port = _parse_endpoint(falkordb_host, falkordb_port)
    except Exception as e:
        logger.error(f"Failed to parse endpoint: {e}")
        raise ConnectionError(f"Invalid FalkorDB endpoint configuration: {e}")

    # Ensure host and port are valid
    if not host or not port:
        logger.error("FALKORDB_HOST and FALKORDB_PORT must be set and valid")
        raise ConnectionError("FALKORDB_HOST and FALKORDB_PORT must be set and valid in environment variables")

    # Get authentication credentials
    username = os.getenv("FALKORDB_USERNAME")
    password = os.getenv("FALKORDB_PASSWORD")

    # Determine SSL configuration
    ssl_env = os.getenv("FALKORDB_SSL", "false").lower()
    ssl = ssl_env in ("true", "1", "yes")

    logger.info(f"Connecting to FalkorDB at {host}:{port} (SSL: {ssl})")
    logger.info(f"Username: {username}, Password: {'***' if password else 'None'}")

    # Create connection parameters
    conn_params = {
        "host": host,
        "port": port,
    }

    if username and password:
        conn_params["username"] = username
        conn_params["password"] = password

    if ssl:
        conn_params["ssl"] = True

    try:
        # First attempt: try with configured SSL
        client = FalkorDB(**conn_params)

        # Test connection with a simple query
        test_graph = client.select_graph("graphtriage_test")
        test_graph.query("RETURN 1 as test")

        logger.info("Successfully connected to FalkorDB")
        return client

    except Exception as e:
        logger.warning(f"Initial connection attempt failed: {e}")

        # If SSL was configured, try without SSL as fallback
        if ssl:
            logger.info("Attempting fallback connection without SSL")
            fallback_params = conn_params.copy()
            fallback_params.pop("ssl", None)

            try:
                client = FalkorDB(**fallback_params)
                test_graph = client.select_graph("graphtriage_test")
                test_graph.query("RETURN 1 as test")

                logger.info("Successfully connected to FalkorDB with SSL fallback")
                return client

            except Exception as fallback_e:
                logger.error(f"SSL fallback connection also failed: {fallback_e}")
                raise ConnectionError(
                    f"Unable to connect to FalkorDB at {host}:{port}. "
                    f"Initial error: {e}. "
                    f"SSL fallback error: {fallback_e}. "
                    f"Please check your FalkorDB credentials and network connectivity."
                )
        else:
            raise ConnectionError(
                f"Unable to connect to FalkorDB at {host}:{port}. "
                f"Error: {e}. "
                f"Please check your FalkorDB credentials and network connectivity."
            )

def test_connection() -> dict:
    """Test connection to FalkorDB and return connection details.

    Returns:
        Dictionary with connection status and metrics
    """
    import time

    start_time = time.time()
    try:
        client = get_falkordb_client()
        test_graph = client.select_graph("graphtriage_smoketest")

        # Test write operation
        test_graph.query("CREATE (t:TestNode {id: 'test', timestamp: $now}) RETURN t",
                        {"now": time.time()})

        # Test read operation
        result = test_graph.query("MATCH (t:TestNode) RETURN t.id as id")

        # Cleanup
        test_graph.query("MATCH (t:TestNode {id: 'test'}) DELETE t")

        end_time = time.time()
        run_time_ms = (end_time - start_time) * 1000

        return {
            "status": "success",
            "connection_string": f"{client.host}:{client.port}",
            "run_time_ms": round(run_time_ms, 2),
            "message": "Successfully connected to FalkorDB cloud"
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "run_time_ms": None,
            "message": "Failed to connect to FalkorDB cloud"
        }

if __name__ == "__main__":
    # Quick test when run directly
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    print("Testing FalkorDB connection...")
    result = test_connection()

    if result["status"] == "success":
        print(f"✅ {result['message']}")
        print(f"   Connection: {result['connection_string']}")
        print(f"   Response time: {result['run_time_ms']}ms")
    else:
        print(f"❌ {result['message']}")
        print(f"   Error: {result['error']}")
        exit(1)