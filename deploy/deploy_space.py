"""Upload the app to a Hugging Face Space (Docker SDK).

NOTE (Oct 2026): Docker Spaces now require a Hugging Face PRO subscription,
so the live demo is hosted on Render instead (see render.yaml). This script
is kept for anyone with PRO.

One-time setup (in your own terminal, so the token never leaves your machine):
    pip install huggingface_hub
    hf auth login

Then from the repo root:
    python deploy/deploy_space.py

Hugging Face builds the Dockerfile in the cloud. Watch the build log on the
Space's page; the first build takes a few minutes.
"""

from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
SPACE_NAME = "motor-insurance-claim-risk"

# Only what the container needs. The data and notebooks stay on GitHub
# (the data isn't ours to redistribute anyway).
FILES = {
    "Dockerfile": "Dockerfile",
    ".dockerignore": ".dockerignore",
    "requirements-api.txt": "requirements-api.txt",
    "models/claim_model.joblib": "models/claim_model.joblib",
    "deploy/SPACE_README.md": "README.md",  # the Space reads its config from README front matter
}


def main() -> None:
    api = HfApi()
    user = api.whoami()["name"]
    repo_id = f"{user}/{SPACE_NAME}"

    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)

    for local, remote in FILES.items():
        api.upload_file(path_or_fileobj=ROOT / local, path_in_repo=remote,
                        repo_id=repo_id, repo_type="space")
    api.upload_folder(folder_path=ROOT / "src", path_in_repo="src", repo_id=repo_id,
                      repo_type="space", ignore_patterns=["__pycache__/*", "*.pyc"])

    print(f"Uploaded. Build log and app: https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()
