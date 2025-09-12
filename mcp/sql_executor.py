# src/cogniquery/mcps/sql_executor.py
import os
import pandas as pd
from sqlalchemy import create_engine, text

from .base import SqlQueryInput, SqlQueryResultOutput
from .secure_file_storage import store_data, StoreDataInput

def _validate_query(sql_query: str) -> bool:
    """Ensures only SELECT statements are executed."""
    return sql_query.strip().lower().startswith("select")

def execute_sql_query(input_data: SqlQueryInput) -> SqlQueryResultOutput:
    """
    Securely executes a read-only SELECT query and returns a handle to the CSV result.
    This tool is secure: it only allows SELECT statements and the database
    connection string is managed securely on the server, never exposed to the agent.
    """
    if not _validate_query(input_data.sql_query):
        return SqlQueryResultOutput(success=False, error_message="Invalid query. Only SELECT statements are allowed.")

    db_uri = (
        os.getenv("DB_CONNECTION_URI")
        or os.getenv("NEONDB_CONN_STR")
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URI")
    )
    if not db_uri:
        return SqlQueryResultOutput(success=False, error_message="Database connection URI is not configured on the server.")

    try:
        engine = create_engine(db_uri)
        with engine.connect() as connection:
            df = pd.read_sql_query(text(input_data.sql_query), connection)
        
        csv_data = df.to_csv(index=False)
        store_input = StoreDataInput(data=csv_data, file_name="sql_result.csv")
        
        # Call the refactored store_data tool
        store_output = store_data(store_input)

        if not store_output.success:
            return SqlQueryResultOutput(success=False, error_message=f"Failed to store query result: {store_output.error_message}")

        return SqlQueryResultOutput(
            success=True,
            file_handle=store_output.file_handle,
            row_count=len(df),
            columns=list(df.columns)
        )
    except Exception as e:
        return SqlQueryResultOutput(success=False, error_message=f"Query execution failed: {e}")

# Legacy class for backward compatibility - will be removed in future versions
class SQLExecutorMCP:
    def __init__(self, storage_mcp=None):
        self._db_uri = os.getenv("DB_CONNECTION_URI")
        if not self._db_uri:
            raise ValueError("DB_CONNECTION_URI environment variable not set.")
        self._engine = create_engine(self._db_uri)
        self._storage_mcp = storage_mcp

    def _validate_query(self, sql_query: str) -> bool:
        """Ensures only SELECT statements are executed."""
        return _validate_query(sql_query)

    def execute(self, input_data: SqlQueryInput) -> SqlQueryResultOutput:
        return execute_sql_query(input_data)
