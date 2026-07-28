from pathlib import Path

import yaml


def test_dockerfile_accepts_build_time_mirrors():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "ARG APT_MIRROR" in dockerfile
    assert "ARG APT_SECURITY_MIRROR" in dockerfile
    assert "ARG PIP_INDEX_URL" in dockerfile
    assert "ARG NPM_CONFIG_REGISTRY" in dockerfile
    assert "http://deb.debian.org/debian" in dockerfile
    assert "pip config set global.index-url" in dockerfile
    assert "npm config set registry" in dockerfile


def test_gitea_workflow_builds_amd64_registry_image_on_tags():
    workflow_path = Path(".gitea/workflows/release-image.yml")
    assert workflow_path.exists()

    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    assert workflow["name"] == "Build And Push Release Image"
    assert workflow["on"]["push"]["tags"] == ["v*"]

    job = workflow["jobs"]["build-and-push"]
    assert job["runs-on"] == "ci"
    assert job["env"]["REGISTRY"] == "192.168.200.101:54453"
    assert job["env"]["IMAGE_REPOSITORY"] == "zhangzhicheng/eric-xhs-spider"
    assert job["env"]["APT_MIRROR"] == "http://mirrors.tuna.tsinghua.edu.cn/debian"
    assert job["env"]["PIP_INDEX_URL"] == "https://pypi.tuna.tsinghua.edu.cn/simple"
    assert job["env"]["NPM_CONFIG_REGISTRY"] == "https://registry.npmmirror.com"

    scripts = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "--platform linux/amd64" in scripts
    assert "--build-arg VERSION=${GITHUB_REF_NAME}" in scripts
    assert "--build-arg APT_MIRROR=${APT_MIRROR}" in scripts
    assert "--build-arg PIP_INDEX_URL=${PIP_INDEX_URL}" in scripts
    assert "--build-arg NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY}" in scripts
    assert "${REGISTRY}/${IMAGE_REPOSITORY}:${GITHUB_REF_NAME}" in scripts
    assert "${REGISTRY}/${IMAGE_REPOSITORY}:latest" in scripts
    assert "${REGISTRY}/${IMAGE_REPOSITORY}:sha-${GITHUB_SHA}" in scripts
