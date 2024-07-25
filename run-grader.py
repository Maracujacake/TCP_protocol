import os
import subprocess

GRADER_REPO = "https://github.com/thotypous/redes-p2-grader"

if os.path.exists("grader"):
    subprocess.run(["git", "-C", "grader", "pull"], check=True)
else:
    subprocess.run(["git", "clone", GRADER_REPO, "grader"], check=True)

subprocess.run(["grader/run"], check=True)
