import compileall
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_training_smoke_test():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["SM_MODEL_DIR"] = tmpdir
        env["MLFLOW_TRACKING_URI"] = f"sqlite:///{Path(tmpdir).as_posix()}/mlflow.db"
        subprocess.run(
            [sys.executable, str(ROOT / "src" / "train.py")],
            check=True,
            env=env,
            cwd=ROOT,
        )
        model_file = Path(tmpdir) / "model.json"
        if not model_file.exists():
            raise RuntimeError("training smoke test did not create model.json")


def main():
    compileall.compile_dir(ROOT / "src", quiet=1, force=True)
    compileall.compile_dir(ROOT / "pipelines", quiet=1, force=True)
    compileall.compile_dir(ROOT / "scripts", quiet=1, force=True)
    compileall.compile_dir(ROOT / "lambda", quiet=1, force=True)
    run_training_smoke_test()
    print("Local lab validation passed.")


if __name__ == "__main__":
    main()
