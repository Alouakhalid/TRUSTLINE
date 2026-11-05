import json
import io
import sys
from contextlib import redirect_stdout, redirect_stderr

nb_path = "ai-engine/ml/notebooks/isolation_forest_training.ipynb"
with open(nb_path) as f:
    nb = json.load(f)

global_ns = {}
exec_count = 1

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        code_text = "".join(cell["source"])
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        
        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code_text, global_ns)
            out_str = stdout_buf.getvalue()
            err_str = stderr_buf.getvalue()
            
            outputs = []
            if out_str:
                outputs.append({
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [line + "\n" for line in out_str.splitlines()]
                })
            if err_str:
                outputs.append({
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [line + "\n" for line in err_str.splitlines()]
                })
            cell["outputs"] = outputs
            cell["execution_count"] = exec_count
            print(f"Executed Cell {exec_count}: Success")
            exec_count += 1
        except Exception as e:
            print(f"Error in Cell {exec_count}: {e}")
            raise

with open(nb_path, "w") as f:
    json.dump(nb, f, indent=1)

print("Notebook execution completed and saved.")
