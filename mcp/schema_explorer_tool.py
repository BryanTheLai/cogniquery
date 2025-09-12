# src/cogniquery/mcps/schema_explorer_tool.py
import os
import re
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from typing import Dict, List, Optional

from .base import SchemaExplorerInput, SchemaExplorerOutput


class DatabaseSchemaQueries:
    """Database-specific schema query provider."""
    
    @staticmethod
    def get_queries(db_type: str) -> Dict[str, str]:
        """Get database-specific schema queries."""
        queries = {
            "postgresql": {
                "columns": """
                    SELECT table_name, column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position;
                """,
                "primary_keys": """
                    SELECT tc.table_name, kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.constraint_type = 'PRIMARY KEY' 
                        AND tc.table_schema = 'public'
                    ORDER BY tc.table_name, kcu.ordinal_position;
                """,
                "foreign_keys": """
                    SELECT
                        tc.table_name as source_table,
                        kcu.column_name as source_column,
                        ccu.table_name as target_table,
                        ccu.column_name as target_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu 
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY' 
                        AND tc.table_schema = 'public'
                    ORDER BY tc.table_name, kcu.column_name;
                """
            },
            "mysql": {
                "columns": """
                    SELECT table_name, column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE()
                    ORDER BY table_name, ordinal_position;
                """,
                "primary_keys": """
                    SELECT table_name, column_name
                    FROM information_schema.key_column_usage
                    WHERE constraint_name = 'PRIMARY' 
                        AND table_schema = DATABASE()
                    ORDER BY table_name, ordinal_position;
                """,
                "foreign_keys": """
                    SELECT
                        table_name as source_table,
                        column_name as source_column,
                        referenced_table_name as target_table,
                        referenced_column_name as target_column
                    FROM information_schema.key_column_usage
                    WHERE referenced_table_name IS NOT NULL
                        AND table_schema = DATABASE()
                    ORDER BY table_name, column_name;
                """
            },
            "sqlite": {
                "columns": """
                    SELECT 
                        m.name as table_name,
                        p.name as column_name,
                        p.type as data_type,
                        CASE WHEN p."notnull" = 0 THEN 'YES' ELSE 'NO' END as is_nullable,
                        p.dflt_value as column_default
                    FROM sqlite_master m
                    LEFT OUTER JOIN pragma_table_info(m.name) p ON m.name != p.name
                    WHERE m.type = 'table' AND m.name NOT LIKE 'sqlite_%'
                    ORDER BY m.name, p.cid;
                """,
                # SQLite doesn't have standard information_schema, so we'll use simpler queries
                "primary_keys": "",
                "foreign_keys": ""
            }
        }
        
        return queries.get(db_type.lower(), queries["postgresql"])


def _execute_query(query: str, engine) -> pd.DataFrame:
    """Execute a query and return results as DataFrame."""
    if not query.strip():
        return pd.DataFrame()
    
    try:
        with engine.connect() as connection:
            return pd.read_sql_query(text(query), connection)
    except Exception as e:
        print(f"Query execution error: {e}")
        return pd.DataFrame()


def _get_database_type(connection_string: str) -> str:
    """Detect database type from connection string."""
    if connection_string.startswith('postgresql://') or connection_string.startswith('postgres://'):
        return 'postgresql'
    elif connection_string.startswith('mysql://'):
        return 'mysql'
    elif connection_string.startswith('sqlite://'):
        return 'sqlite'
    else:
        # Default to postgresql if can't detect
        return 'postgresql'


def _use_sqlalchemy_inspector(engine, table_filter: str = "") -> tuple:
    """Use SQLAlchemy inspector as fallback for schema information."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if table_filter:
        pattern = re.compile(table_filter, re.IGNORECASE)
        tables = [t for t in tables if pattern.search(t)]
    
    columns_data = []
    pk_data = []
    fk_data = []
    
    for table_name in tables:
        # Get columns
        columns = inspector.get_columns(table_name)
        for col in columns:
            columns_data.append({
                'table_name': table_name,
                'column_name': col['name'],
                'data_type': str(col['type']),
                'is_nullable': 'YES' if col.get('nullable', True) else 'NO',
                'column_default': col.get('default', None)
            })
        
        # Get primary keys
        pk_constraint = inspector.get_pk_constraint(table_name)
        if pk_constraint and pk_constraint.get('constrained_columns'):
            for col_name in pk_constraint['constrained_columns']:
                pk_data.append({
                    'table_name': table_name,
                    'column_name': col_name
                })
        
        # Get foreign keys
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            for i, col_name in enumerate(fk['constrained_columns']):
                fk_data.append({
                    'source_table': table_name,
                    'source_column': col_name,
                    'target_table': fk['referred_table'],
                    'target_column': fk['referred_columns'][i] if i < len(fk['referred_columns']) else ''
                })
    
    return (
        pd.DataFrame(columns_data),
        pd.DataFrame(pk_data),
        pd.DataFrame(fk_data)
    )


def explore_database_schema(input_data: SchemaExplorerInput) -> SchemaExplorerOutput:
    """
    Explores database schema in a database-agnostic way.
    
    This tool automatically detects the database type and uses appropriate
    queries to extract schema information including tables, columns, 
    primary keys, and foreign key relationships.
    """
    # Get connection string
    connection_string = input_data.connection_string
    if not connection_string:
        # Try common environment variables
        connection_string = (
            os.getenv("DB_CONNECTION_URI") or 
            os.getenv("NEONDB_CONN_STR") or 
            os.getenv("DATABASE_URL")
        )
    
    if not connection_string:
        return SchemaExplorerOutput(
            success=False, 
            error_message="No database connection string provided. Set DB_CONNECTION_URI environment variable or provide connection_string parameter."
        )
    
    try:
        engine = create_engine(connection_string)
        
        # Detect or use provided database type
        detected_db_type = _get_database_type(connection_string)
        db_type = input_data.database_type if input_data.database_type != "postgresql" else detected_db_type
        
        # Get database-specific queries
        queries = DatabaseSchemaQueries.get_queries(db_type)
        
        # Try database-specific queries first
        columns_df = _execute_query(queries["columns"], engine)
        pk_df = _execute_query(queries["primary_keys"], engine) if input_data.include_relationships else pd.DataFrame()
        fk_df = _execute_query(queries["foreign_keys"], engine) if input_data.include_relationships else pd.DataFrame()
        
        # If queries failed or returned empty, use SQLAlchemy inspector as fallback
        if columns_df.empty:
            columns_df, pk_df, fk_df = _use_sqlalchemy_inspector(engine, input_data.table_filter)
        
        if columns_df.empty:
            return SchemaExplorerOutput(
                success=False,
                error_message="No schema information could be retrieved from the database."
            )
        
        # Apply table filter if provided
        if input_data.table_filter:
            pattern = re.compile(input_data.table_filter, re.IGNORECASE)
            columns_df = columns_df[columns_df['table_name'].str.contains(pattern, regex=True, na=False)]
            if not pk_df.empty:
                pk_df = pk_df[pk_df['table_name'].str.contains(pattern, regex=True, na=False)]
            if not fk_df.empty:
                fk_df = fk_df[fk_df['source_table'].str.contains(pattern, regex=True, na=False)]
        
        # Build schema information string
        schema_info = _build_schema_string(columns_df, pk_df, fk_df, db_type, input_data.include_relationships)
        
        return SchemaExplorerOutput(
            success=True,
            schema_info=schema_info,
            table_count=len(columns_df['table_name'].unique()),
            column_count=len(columns_df),
            relationship_count=len(fk_df) if not fk_df.empty else 0
        )
        
    except Exception as e:
        return SchemaExplorerOutput(
            success=False,
            error_message=f"Schema exploration failed: {str(e)}"
        )


def _build_schema_string(columns_df: pd.DataFrame, pk_df: pd.DataFrame, fk_df: pd.DataFrame, 
                        db_type: str, include_relationships: bool) -> str:
    """Build a comprehensive schema information string."""
    schema_str = f"=== DATABASE SCHEMA ANALYSIS ({db_type.upper()}) ===\n\n"
    
    # Get all tables
    tables = columns_df['table_name'].unique()
    
    # Primary keys lookup
    pk_lookup = {}
    if not pk_df.empty:
        for _, row in pk_df.iterrows():
            table = row['table_name']
            if table not in pk_lookup:
                pk_lookup[table] = []
            pk_lookup[table].append(row['column_name'])
    
    # Foreign keys lookup
    fk_lookup = {}
    if include_relationships and not fk_df.empty:
        for _, row in fk_df.iterrows():
            table = row['source_table']
            if table not in fk_lookup:
                fk_lookup[table] = []
            fk_lookup[table].append({
                'source_column': row['source_column'],
                'target_table': row['target_table'],
                'target_column': row['target_column']
            })
    
    # Build detailed schema for each table
    for table in sorted(tables):
        table_columns = columns_df[columns_df['table_name'] == table]
        schema_str += f"📊 TABLE: {table}\n"
        
        # Columns
        for _, col in table_columns.iterrows():
            pk_indicator = " (PK)" if table in pk_lookup and col['column_name'] in pk_lookup[table] else ""
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            default = f", DEFAULT: {col['column_default']}" if pd.notna(col['column_default']) else ""
            schema_str += f"  • {col['column_name']}: {col['data_type']}{pk_indicator} ({nullable}{default})\n"
        
        # Foreign keys
        if include_relationships and table in fk_lookup:
            schema_str += f"  Foreign Keys:\n"
            for fk in fk_lookup[table]:
                schema_str += f"    • {fk['source_column']} -> {fk['target_table']}.{fk['target_column']}\n"
        
        schema_str += "\n"
    
    # Add relationships summary
    if include_relationships and not fk_df.empty:
        schema_str += "🔗 TABLE RELATIONSHIPS:\n"
        for _, row in fk_df.iterrows():
            schema_str += f"  • {row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']}\n"
        schema_str += "\n"
    
    # Add summary statistics
    schema_str += f"📈 SCHEMA SUMMARY:\n"
    schema_str += f"  - Database Type: {db_type.upper()}\n"
    schema_str += f"  - Total tables: {len(tables)}\n"
    schema_str += f"  - Total columns: {len(columns_df)}\n"
    schema_str += f"  - Primary key constraints: {len(pk_df)}\n"
    if include_relationships:
        schema_str += f"  - Foreign key relationships: {len(fk_df)}\n"
    
    return schema_str
