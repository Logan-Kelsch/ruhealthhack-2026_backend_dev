"""Execute the offline presenter notebook and export a private HTML walkthrough."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.study.workflow import private_path


def export(output: Path, *, in_process: bool = False) -> dict:
    import nbformat
    from nbclient import NotebookClient
    from nbconvert import HTMLExporter
    output = private_path(output)
    if output.exists():
        raise ValueError('use a new export directory outside Git')
    output.mkdir(parents=True, mode=0o700)
    source = ROOT / 'backend_kelsch/notebooks/10_clinical_presenter_demo.ipynb'
    notebook = nbformat.read(source, as_version=4)
    config = next(c.source for c in notebook.cells if c.cell_type == 'code')
    if 'RUN_LIVE_BEDROCK = False' not in config or 'LIVE_REPORT_PATH = None' not in config or 'LIVE_TRACE_PATH = None' not in config:
        raise ValueError('export requires the pristine offline configuration; keep live notebooks private')
    # The kernel uses this interpreter's environment; no kernel installation or .env export.
    env = os.environ.copy()
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
    env['ROUNDS_NOTEBOOK_PRIVATE_BASE'] = str(output / 'runs')
    env['LLM_ENABLED'] = 'false'
    if in_process:
        # Explicit alternative for hosts that block Jupyter's ZMQ transport.
        # It still executes each actual cell and captures IPython rich displays.
        from IPython.terminal.interactiveshell import TerminalInteractiveShell
        from IPython.utils.capture import capture_output
        shell = TerminalInteractiveShell.instance(simple_prompt=True)
        shell.display_formatter.active_types = ['text/plain', 'text/html', 'image/png', 'image/svg+xml']
        shell.user_ns['get_ipython'] = lambda: shell
        previous = {k: os.environ.get(k) for k in ('ROUNDS_NOTEBOOK_PRIVATE_BASE', 'LLM_ENABLED')}
        os.environ.update({k: env[k] for k in previous})
        try:
            for index, cell in enumerate((c for c in notebook.cells if c.cell_type == 'code'), 1):
                with capture_output(display=True) as captured:
                    result = shell.run_cell(cell.source, store_history=True)
                if result.error_before_exec or result.error_in_exec:
                    raise RuntimeError(f'Notebook code cell {index} failed') from (result.error_before_exec or result.error_in_exec)
                cell.execution_count = index
                cell.outputs = []
                for stream, value in (('stdout', captured.stdout), ('stderr', captured.stderr)):
                    if value:
                        cell.outputs.append(nbformat.v4.new_output('stream', name=stream, text=value))
                for display in captured.outputs:
                    cell.outputs.append(nbformat.v4.new_output('display_data', data=display.data, metadata=display.metadata))
            executed = notebook
        finally:
            for k, value in previous.items():
                if value is None: os.environ.pop(k, None)
                else: os.environ[k] = value
    else:
        client = NotebookClient(notebook, timeout=180, kernel_name='python3', resources={'metadata': {'path': str(ROOT)}})
        executed = client.execute(env=env, cwd=str(ROOT))
    nbformat.write(executed, output / 'executed_presenter.ipynb')
    body, _ = HTMLExporter(template_name='lab', exclude_input=True,
                           exclude_input_prompt=True, exclude_output_prompt=True).from_notebook_node(executed)
    (output / 'presenter_demo.html').write_text(body)
    code = [c for c in executed.cells if c.cell_type == 'code']
    images = sum('image/png' in o.get('data', {}) for c in code for o in c.outputs)
    receipt = {'scope': 'Executed offline clinical-facing presentation; no Bedrock call or clinical approval',
               'notebook_sha256': sha256(source.read_bytes()).hexdigest(),
               'exporter_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
               'presenter_module_sha256': sha256((ROOT / 'backend_kelsch/app/study/presenter.py').read_bytes()).hexdigest(),
               'method': 'Sequential in-process IPython execution with captured rich displays' if in_process else 'Native Jupyter kernel execution through nbclient',
               'code_cells_passed': len(code), 'embedded_pngs': images,
               'output_error_cells': sum(o.output_type == 'error' for c in code for o in c.outputs),
               'preview': 'presenter_demo.html', 'executed_notebook': 'executed_presenter.ipynb'}
    (output / 'execution_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--in-process', action='store_true', help='Explicit IPython fallback for hosts blocking kernel transport')
    args = parser.parse_args()
    receipt = export(args.output, in_process=args.in_process)
    print(json.dumps(receipt | {'output_directory': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
