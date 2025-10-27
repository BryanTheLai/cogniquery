# src/cogniquery/mcps/e2b_code_interpreter.py
import os
try:
    from e2b_code_interpreter import Sandbox  # newer SDKs
except Exception:  # pragma: no cover - fallback for older SDKs
    from e2b_code_interpreter import CodeInterpreter as Sandbox

from .base import CodeInterpreterInput, CodeInterpreterOutput, RetrieveDataInput
from .secure_file_storage import retrieve_data, store_data, StoreDataInput

def execute_code_in_sandbox(input_data: CodeInterpreterInput) -> CodeInterpreterOutput:
    """
    Executes Python code in a secure E2B sandbox environment with access to uploaded data.
    This tool provides isolated code execution with data analysis capabilities.
    """
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        return CodeInterpreterOutput(success=False, error_message="E2B_API_KEY environment variable not set.")

    # 1. Retrieve the data using the file handle
    retrieve_input = RetrieveDataInput(file_handle=input_data.file_handle)
    retrieved_data = retrieve_data(retrieve_input)
    if not retrieved_data.success:
        return CodeInterpreterOutput(success=False, error_message=f"Failed to retrieve data: {retrieved_data.error_message}")

    data_content = retrieved_data.data
    
    try:
        # 2. Start the E2B Code Interpreter Sandbox
        # Do not pass api_key directly; the SDK reads E2B_API_KEY from environment
        with Sandbox() as sandbox:
            # 3. Write the data to a file in the sandbox using Python code
            # First, encode the data content for safe embedding in Python code
            import base64
            data_encoded = base64.b64encode(data_content.encode('utf-8')).decode('utf-8')
            
            # Create the data file setup code without nested f-strings
            setup_code = (
                "import base64\n"
                "import pandas as pd\n"
                "import matplotlib.pyplot as plt\n"
                "import json\n"
                "import os\n"
                "\n"
                "# Create the data file from encoded content\n"
                "data_content = base64.b64decode('" + data_encoded + "').decode('utf-8')\n"
                "with open('/tmp/data.csv', 'w', encoding='utf-8') as f:\n"
                "    f.write(data_content)\n"
                "\n"
                "# Ensure output directory exists for charts\n"
                "try:\n"
                "    os.makedirs('output', exist_ok=True)\n"
                "except Exception as _e:\n"
                "    print('Warning: could not create output dir: ' + str(_e))\n"
                "\n"
                "# Read the data\n"
                "try:\n"
                "    df = pd.read_csv('/tmp/data.csv')\n"
                "    print('Data loaded successfully: ' + str(df.shape[0]) + ' rows, ' + str(df.shape[1]) + ' columns')\n"
                "except Exception as e:\n"
                "    print('Error reading data: ' + str(e))\n"
                "    df = None\n"
            )
            
            # 4. Execute setup code first
            setup_execution = sandbox.run_code(setup_code)
            if setup_execution.error:
                return CodeInterpreterOutput(
                    success=False, 
                    error_message=f"Failed to setup data file: {setup_execution.error}"
                )
            
            # 5. Execute the user code
            execution = sandbox.run_code(input_data.code)
            
            # 6. Collect results
            stdout = ""
            stderr = ""
            artifacts = []
            
            # Combine setup output with user code output
            if setup_execution.logs and setup_execution.logs.stdout:
                stdout += "\n".join(setup_execution.logs.stdout) + "\n"
            
            # Process execution results
            if execution.results:
                for result in execution.results:
                    if hasattr(result, 'text') and result.text:
                        stdout += result.text + "\n"
                    elif hasattr(result, 'png') and result.png:
                        try:
                            # Use a more descriptive filename for charts
                            chart_count = len([a for a in artifacts if 'chart' in a]) + 1
                            handle_name = f"average_discount_by_segment_region_{chart_count}.png"
                            # Convert binary PNG data to latin1-encoded string for storage
                            png_data = result.png.decode('latin1') if isinstance(result.png, bytes) else result.png
                            store_out = store_data(StoreDataInput(data=png_data, file_name=handle_name))
                            if store_out.success and store_out.file_handle:
                                artifacts.append(store_out.file_handle)
                                stdout += f"\nChart saved: {handle_name} -> {store_out.file_handle}\n"
                        except Exception as e:
                            stdout += f"\nError saving PNG chart: {str(e)}\n"
                    elif hasattr(result, 'jpeg') and result.jpeg:
                        try:
                            chart_count = len([a for a in artifacts if 'chart' in a]) + 1
                            handle_name = f"total_orders_by_segment_region_{chart_count}.jpeg"
                            # Convert binary JPEG data to latin1-encoded string for storage
                            jpeg_data = result.jpeg.decode('latin1') if isinstance(result.jpeg, bytes) else result.jpeg
                            store_out = store_data(StoreDataInput(data=jpeg_data, file_name=handle_name))
                            if store_out.success and store_out.file_handle:
                                artifacts.append(store_out.file_handle)
                                stdout += f"\nChart saved: {handle_name} -> {store_out.file_handle}\n"
                        except Exception as e:
                            stdout += f"\nError saving JPEG chart: {str(e)}\n"
                    elif hasattr(result, 'chart') and result.chart:
                        # Handle structured chart data from E2B
                        try:
                            chart_count = len([a for a in artifacts if 'chart' in a]) + 1
                            chart_title = getattr(result.chart, 'title', f'chart_{chart_count}')
                            # Sanitize title for filename
                            safe_title = ''.join(c for c in chart_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            safe_title = safe_title.replace(' ', '_').lower()
                            handle_name = f"{safe_title}_{chart_count}.png"
                            
                            # If there's also a PNG representation, use that
                            if hasattr(result, 'png') and result.png:
                                # Convert binary PNG data to latin1-encoded string for storage
                                png_data = result.png.decode('latin1') if isinstance(result.png, bytes) else result.png
                                store_out = store_data(StoreDataInput(data=png_data, file_name=handle_name))
                                if store_out.success and store_out.file_handle:
                                    artifacts.append(store_out.file_handle)
                                    stdout += f"\nStructured chart saved: {handle_name} -> {store_out.file_handle}\n"
                        except Exception as e:
                            stdout += f"\nError saving structured chart: {str(e)}\n"
            
            if execution.logs:
                if execution.logs.stdout:
                    stdout += "\n".join(execution.logs.stdout)
                if execution.logs.stderr:
                    stderr = "\n".join(execution.logs.stderr)
            
            success = execution.error is None
            error_message = str(execution.error) if execution.error else None
            
            if execution.error:
                stderr += f"\nExecution Error: {execution.error}"
            
            # 7. Follow-up: capture any files saved by the user's code under output/*.png|*.jpg|*.jpeg
            try:
                post_code = (
                    "import os, glob, base64\n"
                    "paths = glob.glob('output/*.png') + glob.glob('output/*.jpg') + glob.glob('output/*.jpeg')\n"
                    "print(f'__CQ_FOUND_FILES__:{len(paths)}')\n"
                    "for p in paths:\n"
                    "    try:\n"
                    "        with open(p, 'rb') as f:\n"
                    "            b64 = base64.b64encode(f.read()).decode('ascii')\n"
                    "        # Use marker to indicate start and end of artifact\n"
                    "        print('__CQ_ARTIFACT_START__:' + os.path.basename(p))\n"
                    "        print(b64)\n"
                    "        print('__CQ_ARTIFACT_END__')\n"
                    "    except Exception as e:\n"
                    "        print('__CQ_ARTIFACT_ERR__:' + p + ':' + str(e))\n"
                )
                post_exec = sandbox.run_code(post_code)
                
                # Collect all output into a single string for robust parsing
                all_output = []
                if post_exec.logs and post_exec.logs.stdout:
                    all_output.extend(post_exec.logs.stdout)
                if post_exec.results:
                    for r in post_exec.results:
                        if hasattr(r, 'text') and r.text:
                            all_output.append(r.text)
                
                # Join all output and parse artifacts using markers
                full_output = '\n'.join(str(line) for line in all_output if line)
                
                # Parse artifacts using start/end markers
                import re
                artifact_pattern = r'__CQ_ARTIFACT_START__:([^\n]+)\n(.*?)__CQ_ARTIFACT_END__'
                matches = re.findall(artifact_pattern, full_output, re.DOTALL)
                
                stdout += f"\n[DEBUG] Found {len(matches)} chart artifacts\n"
                
                for fname, b64_data in matches:
                    try:
                        fname = fname.strip()
                        # Remove all whitespace and newlines from base64 string
                        b64_clean = b64_data.replace('\n', '').replace('\r', '').replace(' ', '').strip()
                        
                        import base64 as _b64
                        data_bytes = _b64.b64decode(b64_clean)
                        
                        # Remove 'output/' prefix but preserve original filename
                        if fname.startswith('output/'):
                            fname = fname[7:]
                        
                        # Convert binary data to latin1-encoded string for storage
                        data_str = data_bytes.decode('latin1') if isinstance(data_bytes, bytes) else data_bytes
                        store_out = store_data(StoreDataInput(data=data_str, file_name=fname))
                        if store_out.success and store_out.file_handle:
                            artifacts.append(store_out.file_handle)
                            stdout += f"\n✅ Chart saved: {fname} -> {store_out.file_handle}\n"
                    except Exception as e:
                        stdout += f"\n❌ Error parsing artifact {fname}: {str(e)}\n"
                
            except Exception as e:
                stdout += f"\n[ERROR] Artifact capture failed: {str(e)}\n"
            
            return CodeInterpreterOutput(
                success=success, 
                stdout=stdout.strip(), 
                stderr=stderr.strip() if stderr else "", 
                artifacts=artifacts,
                error_message=error_message
            )
            
    except Exception as e:
        return CodeInterpreterOutput(success=False, error_message=f"An error occurred during sandbox execution: {e}")

# Legacy class for backward compatibility - will be removed in future versions
class E2BCodeInterpreterMCP:
    def __init__(self, storage_mcp=None):
        self._api_key = os.getenv("E2B_API_KEY")
        if not self._api_key:
            raise ValueError("E2B_API_KEY environment variable not set.")
        self._storage_mcp = storage_mcp

    def execute(self, input_data: CodeInterpreterInput) -> CodeInterpreterOutput:
        return execute_code_in_sandbox(input_data)
