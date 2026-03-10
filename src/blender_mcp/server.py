"""BlenderMCP server: lifecycle management and Blender socket connection.

Manages the persistent TCP connection to the Blender addon socket server,
provides the `get_blender_connection` helper used by all MCP tool modules,
and wires up the FastMCP server lifespan.
"""
import json
import logging
import os
import socket
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP

from .mcp_instance import mcp

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BlenderMCPServer")

@dataclass
class BlenderConnection:
    host: str
    port: int
    sock: socket.socket = None 
    
    def connect(self) -> bool:
        """Connect to the Blender addon socket server"""
        if self.sock:
            return True
            
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Blender at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Blender: {str(e)}")
            self.sock = None
            return False
    
    def disconnect(self):
        """Disconnect from the Blender addon"""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from Blender: {str(e)}")
            finally:
                self.sock = None
    
    def receive_full_response(self, sock, buffer_size=8192):
        """Receive the complete response, potentially in multiple chunks"""
        buffer = bytearray()
        
        while True:
            try:
                chunk = sock.recv(buffer_size)
                if not chunk:
                    break
                buffer.extend(chunk)
                try:
                    json.loads(buffer.decode('utf-8'))
                    break
                except json.JSONDecodeError:
                    pass
            except TimeoutError:
                logger.error("Socket timeout while receiving data")
                raise Exception("Timeout while receiving data from Blender") from None
        
        return bytes(buffer)
    
    def _is_connected(self) -> bool:
        """Check whether the socket is still alive without blocking."""
        if not self.sock:
            return False
        try:
            self.sock.setblocking(False)
            data = self.sock.recv(1, socket.MSG_PEEK)
            self.sock.setblocking(True)
            return len(data) > 0
        except BlockingIOError:
            self.sock.setblocking(True)
            return True
        except Exception:
            self.sock = None
            return False

    def send_command(self, command_type: str, params: dict[str, Any] = None) -> dict[str, Any]:
        """Send a command to Blender and return the response.

        Automatically reconnects once if the socket is stale (e.g. after a
        Windsurf window reload that left the previous connection open).
        """
        if not self._is_connected():
            logger.warning("Socket is stale or missing — reconnecting")
            self.disconnect()
            if not self.connect():
                raise ConnectionError("Not connected to Blender")

        command = {"type": command_type, "params": params or {}}

        try:
            logger.info(f"Sending command: {command_type} with params: {params}")

            self.sock.sendall(json.dumps(command).encode('utf-8'))
            logger.info("Command sent, waiting for response...")

            self.sock.settimeout(120.0)
            response_data = self.receive_full_response(self.sock)
            logger.info(f"Received {len(response_data)} bytes of data")

            response = json.loads(response_data.decode('utf-8'))
            logger.info(f"Response status: {response.get('status')}")

            if response.get('status') == 'error':
                error_msg = response.get('message', 'Unknown error')
                logger.error(f"Blender returned error: {error_msg}")
                return {"error": error_msg}

            return response.get('result', {})

        except OSError as e:
            logger.error(f"Socket connection error: {str(e)}")
            self.sock = None
            raise Exception(f"Connection to Blender lost: {str(e)}") from e

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Blender: {str(e)}")
            if 'response_data' in locals() and response_data:
                logger.error(f"Raw response (first 200 bytes): {response_data[:200]}")
            raise Exception(f"Invalid response from Blender: {str(e)}") from e

        except Exception as e:
            logger.error(f"Error communicating with Blender: {str(e)}")
            self.sock = None
            raise Exception(f"Communication error with Blender: {str(e)}") from e

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    
    startup_start = time.time()
    logger.info("BlenderMCP server starting up")
    
    blender_start = time.time()
    try:
        get_blender_connection()
        blender_time = time.time() - blender_start
        logger.info(f"Successfully connected to Blender on startup ({blender_time:.2f}s)")
    except Exception as e:
        blender_time = time.time() - blender_start
        logger.warning(f"Could not connect to Blender on startup ({blender_time:.2f}s): {str(e)}")
        logger.warning("Make sure the Blender addon is running before using Blender resources or tools")

    logger.info(f"Server startup complete ({time.time() - startup_start:.2f}s)")
    try:
        yield {}
    finally:
        global _blender_connection
        if _blender_connection:
            logger.info("Disconnecting from Blender on shutdown")
            _blender_connection.disconnect()
            _blender_connection = None
        logger.info("BlenderMCP server shut down")
        
mcp.lifespan = server_lifespan

_blender_connection = None

def get_blender_connection():
    """Get or create a persistent Blender connection"""
    global _blender_connection
    
    if not _blender_connection:
        port = int(os.environ.get("BLENDER_MCP_PORT", "9876"))
        host = os.environ.get("BLENDER_MCP_HOST", "localhost")
        
        logger.info(f"Creating new connection to Blender on {host}:{port}")
        _blender_connection = BlenderConnection(host=host, port=port)
        
        if not _blender_connection.connect():
            logger.error("Failed to connect to Blender")
            _blender_connection = None
            raise Exception("Could not connect to Blender. Make sure the Blender addon is running.")
        logger.info("Created new persistent connection to Blender")
    
    return _blender_connection

from . import mcp_functions  # noqa: F401 — registers all @mcp.tool() decorators


def main():
    """Run the MCP server"""
    mcp.run()

if __name__ == "__main__":
    main()
