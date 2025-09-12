"""CogniQuery MCP server.

Run with STDIO (default):
	python server.py

Run with HTTP:
	python server.py http

This exposes a minimal set of tools and a Slack post tool.
"""

from __future__ import annotations

import argparse
import base64
import io
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure site-packages takes precedence over project root to avoid
# shadowing the official 'mcp' package by the local './mcp' folder.
try:
	if '' in sys.path:
		sys.path.remove('')
		sys.path.append('')
except Exception:
	pass

from dotenv import load_dotenv

# Avoid shadowing the installed 'mcp' package by local './mcp' folder
_repo_root = str(Path(__file__).resolve().parent)
try:
	if _repo_root in sys.path:
		sys.path.remove(_repo_root)
except Exception:
	pass

from fastmcp import FastMCP

try:
	# slack_bolt installs slack_sdk; use the WebClient directly.
	from slack_sdk import WebClient
	from slack_sdk.errors import SlackApiError
except Exception:  # pragma: no cover - optional import until installed
	WebClient = None  # type: ignore
	SlackApiError = Exception  # type: ignore


# Load env first so tools can read tokens
load_dotenv()


mcp = FastMCP("CogniQuery MCP")


@mcp.tool()
def echo(text: str) -> str:
	"""Return the same text. Useful for a quick sanity check."""
	return text


@mcp.tool()
def slack_post(channel: str, text: str) -> str:
	"""Post a message to a Slack channel.

	Args:
		channel: Slack channel ID (e.g. C0123456789) or DM ID.
		text: Message text to send.

	Returns:
		A short status string.
	"""
	token = (
		os.environ.get("SLACK_BOT_TOKEN")
		or os.environ.get("SLACK_USER_TOKEN")
	)
	if not token:
		return "missing Slack token in env"

	if WebClient is None:  # library not available
		return "slack_sdk not installed"

	try:
		client = WebClient(token=token)
		resp = client.chat_postMessage(channel=channel, text=text)
		if resp.get("ok"):
			return "ok"
		return f"error: {resp}"
	except SlackApiError as e:  # type: ignore[name-defined]
		return f"slack error: {getattr(e, 'response', str(e))}"
	except Exception as e:  # pragma: no cover
		return f"error: {e}"


def _read_bytes_from_handle(file_handle: str) -> bytes:
	"""Read bytes from secure storage by handle without importing local mcp pkg."""
	# Basic validation to avoid traversal
	if not file_handle or ".." in file_handle or "/" in file_handle or "\\" in file_handle:
		raise ValueError("invalid file handle")
	storage_dir = Path(".tmp_secure_storage")
	path = storage_dir / file_handle
	if not path.exists() or not path.is_file():
		raise FileNotFoundError("file not found")
	return path.read_bytes()


@mcp.tool()
def slack_upload(
	channel: str,
	filename: str,
	file_handle: str = "",
	file_path: str = "",
	data_base64: str = "",
	initial_comment: str = "",
	title: str = "",
) -> str:
	"""Upload a file (pdf/image/any) to a Slack channel.

	Provide exactly one of: file_handle, file_path, data_base64.
	- file_handle: handle from secure storage (.tmp_secure_storage)
	- file_path: local path on this server
	- data_base64: base64-encoded bytes
	"""
	token = (
		os.environ.get("SLACK_BOT_TOKEN")
		or os.environ.get("SLACK_USER_TOKEN")
	)
	if not token:
		return "missing Slack token in env"
	if WebClient is None:
		return "slack_sdk not installed"

	# Load bytes from chosen source
	sources = [bool(file_handle), bool(file_path), bool(data_base64)]
	if sum(sources) != 1:
		return "provide exactly one of file_handle, file_path, data_base64"

	try:
		if file_handle:
			data = _read_bytes_from_handle(file_handle)
		elif file_path:
			data = Path(file_path).read_bytes()
		else:
			data = base64.b64decode(data_base64)
	except Exception as e:
		return f"load error: {e}"

	try:
		client = WebClient(token=token)
		# Prefer v2 API
		file_stream = io.BytesIO(data)
		kwargs = dict(
			channel=channel,
			file=file_stream,
			filename=filename,
		)
		if initial_comment:
			kwargs["initial_comment"] = initial_comment
		if title:
			kwargs["title"] = title
		resp = client.files_upload_v2(**kwargs)
		if resp.get("ok"):
			return "ok"
		# Fallback for older param name in some workspaces/SDKs
		kwargs_fallback = kwargs.copy()
		kwargs_fallback.pop("channel", None)
		kwargs_fallback["channels"] = channel
		resp2 = client.files_upload_v2(**kwargs_fallback)
		if resp2.get("ok"):
			return "ok"
		return f"error: {resp2}"
	except SlackApiError as e:  # type: ignore[name-defined]
		return f"slack error: {getattr(e, 'response', str(e))}"
	except Exception as e:
		return f"error: {e}"


# Expose ASGI app for alternative hosting if desired
app = mcp.http_app()


def main(argv: Optional[list[str]] = None) -> None:
	parser = argparse.ArgumentParser(
		description="Run CogniQuery MCP server"
	)
	parser.add_argument(
		"transport",
		nargs="?",
		default="stdio",
		choices=["stdio", "http"],
		help="Transport to use (default: stdio)",
	)
	parser.add_argument(
		"--host",
		default=os.environ.get("MCP_HOST", "127.0.0.1"),
		help="HTTP host (default: 127.0.0.1)",
	)
	parser.add_argument(
		"--port",
		type=int,
		default=int(os.environ.get("MCP_PORT", "8000")),
		help="HTTP port (default: 8000)",
	)
	args = parser.parse_args(argv)

	if args.transport == "http":
		print(
			f"Starting MCP (http) on http://{args.host}:{args.port} ..."
		)
		mcp.run(transport="http", host=args.host, port=args.port)
	else:
		print("Starting MCP (stdio) ...")
		mcp.run()  # stdio is default


if __name__ == "__main__":
	main()
