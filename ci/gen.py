import json
import pathlib

THIS_FILE = pathlib.PurePosixPath(
    pathlib.Path(__file__).relative_to(pathlib.Path().resolve())
)


def gen(content: dict, target: str):
    pathlib.Path(target).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(target).write_text(
        json.dumps(content, indent=2, sort_keys=True), newline="\n"
    )


def gen_dependabot():
    target = ".github/dependabot.yaml"
    content = {
        "version": 2,
        "updates": [
            {
                "package-ecosystem": e,
                "allow": [{"dependency-type": "all"}],
                "directory": "/",
                "schedule": {"interval": "daily"},
            }
            for e in ["github-actions", "uv"]
        ],
    }
    gen(content, target)


def gen_publish_workflow():
    target = ".github/workflows/github-pages.yaml"
    content = {
        "env": {
            "description": f"This workflow ({target}) was generated from {THIS_FILE}"
        },
        "name": "Deploy site",
        "on": {"push": {"branches": ["master"]}, "workflow_dispatch": {}},
        "concurrency": {"cancel-in-progress": True, "group": "github-pages"},
        "jobs": {
            "deploy": {
                "name": "Deploy site",
                "runs-on": "ubuntu-latest",
                "environment": {
                    "name": "github-pages",
                    "url": "${{ steps.deployment.outputs.page_url }}",
                },
                "permissions": {
                    "contents": "read",
                    "pages": "write",
                    "id-token": "write",
                },
                "steps": [
                    {"name": "Check out repository", "uses": "actions/checkout@v5"},
                    {
                        "name": "Configure GitHub Pages",
                        "uses": "actions/configure-pages@v5",
                    },
                    {"name": "Build site", "run": "sh ci/build.sh"},
                    {
                        "name": "Upload artifact",
                        "uses": "actions/upload-pages-artifact@v3",
                        "with": {"path": "output"},
                    },
                    {
                        "name": "Deploy to GitHub Pages",
                        "id": "deployment",
                        "uses": "actions/deploy-pages@v4",
                    },
                ],
            },
        },
    }
    gen(content, target)


def main():
    gen_dependabot()
    gen_publish_workflow()


if __name__ == "__main__":
    main()
