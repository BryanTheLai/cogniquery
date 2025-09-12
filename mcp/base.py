# src/cogniquery/mcps/base.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class BaseMcpInput(BaseModel):
    """Base model for all MCP inputs."""
    pass

class BaseMcpOutput(BaseModel):
    """Base model for all MCP outputs."""
    success: bool
    error_message: str | None = None

# --- File Storage Contracts ---
class StoreDataInput(BaseMcpInput):
    data: str
    file_name: str

class RetrieveDataInput(BaseMcpInput):
    file_handle: str

class FileHandleOutput(BaseMcpOutput):
    file_handle: str | None = None

class RetrievedDataOutput(BaseMcpOutput):
    data: str | None = None
    
# --- SQL Executor Contracts ---
class SqlQueryInput(BaseMcpInput):
    sql_query: str = Field(..., description="A valid SQL SELECT statement.")

class SqlQueryResultOutput(FileHandleOutput):
    """The output is a file handle to the CSV result."""
    row_count: int | None = None
    columns: List[str] | None = None

# --- E2B Code Interpreter Contracts ---
class CodeInterpreterInput(BaseMcpInput):
    code: str = Field(..., description="The Python code to execute.")
    file_handle: str = Field(..., description="The handle to the data file to be used in the code.")

class CodeInterpreterOutput(BaseMcpOutput):
    stdout: str | None = None
    stderr: str | None = None
    artifacts: List[str] = Field(default_factory=list, description="List of filenames for any artifacts created.")

# --- PDF Generator Contracts ---
class PdfInput(BaseMcpInput):
    markdown_content: str
    html_content: str = ""  # If provided, use this HTML directly instead of rendering markdown
    chart_handles: List[str] = Field(default_factory=list)
    data: str = ""  # Required by StoreDataInput inheritance pattern
    file_name: str = ""  # Required by StoreDataInput inheritance pattern

# --- Schema Explorer Contracts ---
class SchemaExplorerInput(BaseMcpInput):
    database_type: str = Field(default="postgresql", description="Database type (postgresql, mysql, sqlite, etc.)")
    connection_string: str = Field(default="", description="Optional custom connection string. If empty, uses environment variable.")
    include_relationships: bool = Field(default=True, description="Whether to include foreign key relationships")
    table_filter: str = Field(default="", description="Optional table name filter (regex pattern)")

class SchemaExplorerOutput(BaseMcpOutput):
    schema_info: str | None = None
    table_count: int | None = None
    column_count: int | None = None
    relationship_count: int | None = None



# --- Slack Reader Contracts ---
class SlackListChannelsInput(BaseMcpInput):
    include_private: bool = Field(default=False, description="Include private channels")
    include_archived: bool = Field(default=False, description="Include archived channels")

class SlackChannel(BaseModel):
    id: str
    name: str
    is_private: bool = False
    is_archived: bool = False
    member_count: int = 0
    purpose: str = ""
    topic: str = ""

class SlackListChannelsOutput(BaseMcpOutput):
    channels: List[SlackChannel] = Field(default_factory=list)
    total_count: int = 0

class SlackSearchMessagesInput(BaseMcpInput):
    query: str = Field(..., description="Search query for messages")
    count: int = Field(default=10, description="Maximum number of messages to return")
    sort: str = Field(default="timestamp", description="Sort order (timestamp, relevance)")
    channel: str = Field(default="", description="Restrict search to specific channel ID")

class SlackFile(BaseModel):
    id: str
    name: str
    title: str = ""
    mimetype: str = ""
    filetype: str = ""
    size: int = 0
    url_private: str = ""
    url_private_download: str = ""
    permalink: str = ""

class SlackMessage(BaseModel):
    text: str
    user: str
    timestamp: str = ""
    ts: str = ""  # Slack timestamp alias
    channel: str = ""
    channel_name: str = ""
    files: List[SlackFile] = Field(default_factory=list)
    thread_ts: str = ""
    reply_count: int = 0
    permalink: str = ""

class SlackSearchMessagesOutput(BaseMcpOutput):
    messages: List[SlackMessage] = Field(default_factory=list)
    total_count: int = 0
    query: str = ""

class SlackFileExtractionInput(BaseMcpInput):
    file_info: Dict[str, Any] = Field(..., description="Slack file information")

class SlackFileExtractionOutput(BaseMcpOutput):
    extracted_text: str = ""
    file_type: str = ""
    file_size: int = 0
    extraction_method: str = ""
