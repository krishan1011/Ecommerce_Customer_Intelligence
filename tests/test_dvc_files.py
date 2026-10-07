import yaml

from src.config import PARAMS, ROOT


def _path_exists(root: dict, dotted_path: str) -> bool:
    current = root
    for component in dotted_path.split("."):
        if not isinstance(current, dict) or component not in current:
            return False
        current = current[component]
    return True


def test_dvc_stages_have_commands_dependencies_and_valid_params():
    pipeline = yaml.safe_load((ROOT / "dvc.yaml").read_text(encoding="utf-8"))
    assert pipeline["stages"]
    for stage_name, stage in pipeline["stages"].items():
        assert stage.get("cmd"), f"{stage_name} is missing cmd"
        assert stage.get("deps"), f"{stage_name} is missing deps"
        for parameter in stage.get("params", []):
            assert _path_exists(
                PARAMS, parameter
            ), f"{stage_name} references unknown params.yaml key {parameter}"
