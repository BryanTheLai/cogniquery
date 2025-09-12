"""CogniQuery MCP server.

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
import site

# Ensure PyPI 'mcp' package takes precedence over local './mcp' directory
try:
	# Remove CWD ''
	if '' in sys.path:
		sys.path.remove('')
	# Promote site-packages to the front
	site_paths = []
	try:
		site_paths.extend(site.getsitepackages())
	except Exception:
		pass
	try:
		user_site = site.getusersitepackages()
		if isinstance(user_site, str):
			site_paths.append(user_site)
	except Exception:
		pass
	for p in reversed([sp for sp in site_paths if sp in sys.path]):
		sys.path.remove(p)
		sys.path.insert(0, p)
	# Demote script directory (repo root) to the end
	script_dir = str(Path(__file__).resolve().parent)
	if script_dir in sys.path:
		sys.path.remove(script_dir)
		sys.path.append(script_dir)
except Exception:
	pass

from dotenv import load_dotenv

from fastmcp import FastMCP
import importlib.util as _ilu
import types as _types

_repo_root = Path(__file__).resolve().parent

def _load_local_module(name: str, relative_path: str):
    file_path = _repo_root / "mcp" / relative_path
    spec = _ilu.spec_from_file_location(name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {name} from {file_path}")
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Ensure a synthetic package exists for 'cq_mcp' so relative imports work
if "cq_mcp" not in sys.modules:
    _pkg = _types.ModuleType("cq_mcp")
    _pkg.__path__ = [str(_repo_root / "mcp")]  # type: ignore[attr-defined]
    sys.modules["cq_mcp"] = _pkg

# Load base first so others can import from .base
_cq_base = _load_local_module("cq_mcp.base", "base.py")
_cq_schema = _load_local_module("cq_mcp.schema_explorer_tool", "schema_explorer_tool.py")
_cq_sql = _load_local_module("cq_mcp.sql_executor", "sql_executor.py")
_cq_pdf = _load_local_module("cq_mcp.pdf_generator", "pdf_generator.py")
_cq_storage = _load_local_module("cq_mcp.secure_file_storage", "secure_file_storage.py")
_cq_e2b = _load_local_module("cq_mcp.e2b_code_interpreter", "e2b_code_interpreter.py")
_cq_web = _load_local_module("cq_mcp.web_search", "web_search.py")

# Re-export types and functions under locals to simplify tool wrappers
SchemaExplorerInput = _cq_base.SchemaExplorerInput
SqlQueryInput = _cq_base.SqlQueryInput
PdfInput = _cq_base.PdfInput
StoreDataInput = _cq_base.StoreDataInput
RetrieveDataInput = _cq_base.RetrieveDataInput
CodeInterpreterInput = _cq_base.CodeInterpreterInput
WebSearchInput = _cq_base.WebSearchInput
ScrapeWebsiteInput = _cq_base.ScrapeWebsiteInput

explore_database_schema = _cq_schema.explore_database_schema
execute_sql_query = _cq_sql.execute_sql_query
generate_pdf_report = _cq_pdf.generate_pdf_report
storage_store_data = _cq_storage.store_data
storage_retrieve_data = _cq_storage.retrieve_data
execute_code_in_sandbox = _cq_e2b.execute_code_in_sandbox
search_the_web = _cq_web.search_the_web
scrape_website = _cq_web.scrape_website
import json

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


# Expose ASGI app for alternative hosting if desired (defined after tool registrations below)


@mcp.tool(name="schema_explorer")
def schema_explorer(
    database_type: str = "postgresql",
    connection_string: str = "",
    include_relationships: bool = True,
    table_filter: str = "",
) -> str:
    inp = SchemaExplorerInput(
        database_type=database_type,
        connection_string=connection_string,
        include_relationships=include_relationships,
        table_filter=table_filter,
    )
    out = explore_database_schema(inp)
    if out.success:
        return out.schema_info or ""
    return f"error: {out.error_message or 'unknown'}"


@mcp.tool(name="sql_executor")
def sql_executor(sql_query: str) -> str:
    out = execute_sql_query(SqlQueryInput(sql_query=sql_query))
    payload = {
        "success": out.success,
        "error_message": out.error_message,
        "file_handle": out.file_handle,
        "row_count": out.row_count,
        "columns": out.columns,
    }
    return json.dumps(payload)


@mcp.tool(name="store_data")
def store_data(data: str, file_name: str) -> str:
    out = storage_store_data(StoreDataInput(data=data, file_name=file_name))
    payload = {
        "success": out.success,
        "error_message": out.error_message,
        "file_handle": out.file_handle,
    }
    return json.dumps(payload)


@mcp.tool(name="retrieve_data")
def retrieve_data(file_handle: str) -> str:
    out = storage_retrieve_data(RetrieveDataInput(file_handle=file_handle))
    payload = {
        "success": out.success,
        "error_message": out.error_message,
        "data": out.data,
    }
    return json.dumps(payload)


@mcp.tool(name="code_interpreter")
def code_interpreter(code: str, file_handle: str) -> str:
    out = execute_code_in_sandbox(CodeInterpreterInput(code=code, file_handle=file_handle))
    payload = {
        "success": out.success,
        "error_message": out.error_message,
        "stdout": out.stdout,
        "stderr": out.stderr,
        "artifacts": out.artifacts,
    }
    return json.dumps(payload)


@mcp.tool(name="generate_pdf_report")
def tool_generate_pdf_report(markdown_content: str, html_content: str = "", chart_handles = "") -> str:
    # Import resolve_chart_handle from the correct local module
    resolve_chart_handle = _cq_storage.resolve_chart_handle
    
    handles = []
    try:
        if isinstance(chart_handles, list):
            handles = chart_handles
        elif chart_handles:
            handles = json.loads(chart_handles)
            if not isinstance(handles, list):
                handles = []
    except Exception:
        handles = []
    
    # Resolve chart handles from original filenames to UUID handles
    resolved_handles = []
    for handle in handles:
        resolved = resolve_chart_handle(handle)
        if resolved:
            resolved_handles.append(resolved)
    
    out = generate_pdf_report(PdfInput(markdown_content=markdown_content, html_content=html_content, chart_handles=resolved_handles))
    payload = {
        "success": out.success,
        "error_message": out.error_message,
        "file_handle": out.file_handle,
    }
    return json.dumps(payload)


@mcp.tool(name="web_search")
def web_search(query: str) -> str:
    out = search_the_web(WebSearchInput(query=query))
    payload = out.model_dump() if hasattr(out, "model_dump") else {}
    return json.dumps(payload)


@mcp.tool(name="scrape_website")
def tool_scrape_website(url: str) -> str:
    out = scrape_website(ScrapeWebsiteInput(url=url))
    payload = out.model_dump() if hasattr(out, "model_dump") else {}
    return json.dumps(payload)

# Expose ASGI app for alternative hosting if desired (now that all tools are registered)
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
			f"Starting MCP (http) on http://{args.host}:{args.port}/mcp ..."
		)
		mcp.run(transport="http", host=args.host, port=args.port, path="/mcp")
	else:
		print("Starting MCP (stdio) ...")
		mcp.run()  # stdio is default


if __name__ == "__main__":
	main()
