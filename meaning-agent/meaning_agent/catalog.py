"""Static read-only MCP resource catalog; never resolves user paths."""

from .constants import EVIDENCE_LEVELS, PROVENANCE, SCALES
from .i18n import bi
from .skills.registry import registry_metadata

SKILL_WORKFLOWS = {
    "reduce-cognitive-load": bi("分离断言与问题，保留未验证标记和原文。", "Separate assertions from questions; retain unverified markers and source text."),
    "model-experiential-interface": bi("建议无脚本 HTML 与可调参数；不执行原型。", "Suggest script-free HTML and adjustable parameters; never execute the prototype."),
    "map-direction-value-boundary": bi("抽取方向、价值、边界与连续光谱；不替人选择。", "Extract direction, value, boundaries, and a continuous spectrum; never choose for a human."),
    "grade-evidence-falsification": bi("使用 E0–E6 保守标注并给出证伪计划；不认定实证状态。", "Use conservative E0–E6 labels and falsification plans; never assert empirical status."),
    "calibrate-five-scales": bi("检查五尺度冲突、优先级、成本和触发条件；禁止加权求和。", "Inspect five-scale conflicts, priorities, costs, and triggers; forbid weighted summation."),
    "recursive-review-zeroing": bi("最多三轮递归审视，提供可逆归零；不删除数据或执行操作。", "Use up to three recursive review passes and reversible zeroing; never delete data or execute actions."),
}


def _resource(uri, name, description):
    return {"uri": uri, "name": name, "description": description, "mimeType": "application/json"}


RESOURCES = [
    _resource("meaning://catalog", "Meaning Intelligence Catalog / 意义智能目录", bi("六技能、证据、尺度与安全边界。", "Six skills, evidence, scales, and safety boundaries.")),
    _resource("meaning://evidence", "Evidence E0–E6 / 证据 E0–E6", bi("证据定义与保守标注规则。", "Evidence definitions and conservative labeling rules.")),
    _resource("meaning://scales", "Five Scales / 五尺度", bi("五个不可通约、不可加权求和的尺度。", "Five incommensurable scales that cannot be weight-summed.")),
    _resource("meaning://safety", "Safety and Approval / 安全与批准", bi("只读、本地、人工批准和无凭据泄露边界。", "Read-only, local, human approval, and no-credential-leak boundaries.")),
]
for spec in registry_metadata():
    uri = "meaning://skills/" + spec["name"]
    RESOURCES.append(_resource(uri, spec["name"], bi(spec["description"], spec["description_en"])))


def resource_catalog():
    return {
        "schema_version": "1.0.0",
        "title": bi("意义智能只读资源目录", "Meaning Intelligence read-only resource catalog"),
        "description": bi("所有 URI 均为虚拟标识，不映射文件路径。", "All URIs are virtual identifiers and do not map to file paths."),
        "resources": RESOURCES,
        "tools": ["meaning_analyze", "meaning_review"],
    }


def read_resource(uri):
    if uri == "meaning://catalog":
        return resource_catalog()
    if uri == "meaning://evidence":
        return {
            "title": bi("证据等级", "Evidence levels"),
            "levels": [{"id": item["id"], "name": bi(item["name"], item["name_en"]), "definition": bi(item["definition"], item["definition_en"])} for item in EVIDENCE_LEVELS],
            "policy": bi("缺少材料时 E0 只是保守占位，真实状态仍为未知。", "Without materials, E0 is only a conservative placeholder; real status remains unknown."),
        }
    if uri == "meaning://scales":
        return {
            "title": bi("五尺度", "Five scales"),
            "scales": [{"id": key, "name": bi(zh, en)} for key, zh, en in SCALES],
            "aggregation": "weighted_summation_forbidden",
            "reason": bi("尺度不可通约，禁止补偿性加总。", "Scales are incommensurable; compensatory aggregation is forbidden."),
        }
    if uri == "meaning://safety":
        return {
            "title": bi("安全边界", "Safety boundaries"),
            "rules": [
                bi("默认离线、确定性、只读。", "Offline, deterministic, and read-only by default."),
                bi("Web 仅绑定 127.0.0.1；无任意文件或命令接口。", "Web binds only to 127.0.0.1; no arbitrary file or command interface."),
                bi("LLM 仅使用显式配置端点；不重定向，不记录密钥。", "LLM uses only the configured endpoint, no redirects, and no key logging."),
                bi("人类批准默认 pending；批准不授权执行。", "Human approval defaults to pending; approval never authorizes execution."),
            ],
            "provenance": PROVENANCE,
        }
    prefix = "meaning://skills/"
    if uri.startswith(prefix):
        name = uri[len(prefix):]
        spec = next((item for item in registry_metadata() if item["name"] == name), None)
        if spec:
            return {
                "uri": uri,
                "skill": spec,
                "workflow": SKILL_WORKFLOWS[name],
                "approval": "pending_human",
                "implementation": spec["implementation"],
                "limits": bi("规则启发式，不是实证验证或操作授权。", "Rule heuristics, not empirical validation or execution authorization."),
            }
    return None
