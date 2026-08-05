#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


TRANSIENT_TERMS = {"接电话", "哭泣", "愤怒", "微笑", "走路", "坐下", "站立", "中景", "全景", "特写", "俯视", "仰视"}
# 各资产类型的统一参考图画幅约定（键用 schema 组名复数形式）：
# - characters: 21:9 转面四视图（面部特写 + 正/侧/背全身）
# - scenes: 16:9 Key Plate + 四宫格
# - props: 16:9 单参考图
REFERENCE_LAYOUT_BY_TYPE = {
    "characters": "character_turnaround_21x9_v1",
    "scenes": "scene_keyplate_quad_v1",
    "props": "prop_single_reference_v1",
}
# 生成型资产必须使用对应画幅约定；非生成型（handling_policy=text_prompt_control 等）
# 允许不填 reference_layout，但一旦填写就必须匹配资产类型。
ALLOWED_REFERENCE_LAYOUTS = set(REFERENCE_LAYOUT_BY_TYPE.values())
# 旧数据里出现过 prop 使用 single_reference；为兼容保留为合法但建议升级
LEGACY_REFERENCE_LAYOUTS = {"single_reference"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Flag invalid or suspicious asset variants.")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    path = Path(args.run_dir).resolve() / "outputs/asset_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    errors, warnings = [], []
    ids, names = set(), set()
    for group in ("characters", "scenes", "props"):
        for item in data.get(group, []):
            aid, name = item.get("asset_id"), item.get("asset_name", "")
            if aid in ids or name in names:
                errors.append(f"duplicate asset identity or name: {aid} / {name}")
            ids.add(aid); names.add(name)
            if "状态" in name:
                errors.append(f"forbidden 状态 suffix/token: {name}")
            if group == "characters" and any(term in name for term in TRANSIENT_TERMS):
                warnings.append(f"possible transient character variant: {name}")
            if item.get("generation_required") and not item.get("output_prompt_path"):
                errors.append(f"missing prompt path: {name}")

            # —— 画幅 / reference_layout 硬校验 ——
            layout = item.get("reference_layout")
            if item.get("generation_required") is True:
                expected = REFERENCE_LAYOUT_BY_TYPE.get(group)
                if expected and layout != expected:
                    errors.append(
                        f"{group} 资产 {name} 必须使用参考图约定 {expected}，当前为 {layout!r}"
                    )
            if layout is not None and layout not in ALLOWED_REFERENCE_LAYOUTS | LEGACY_REFERENCE_LAYOUTS:
                errors.append(f"{group} 资产 {name} 使用了未知 reference_layout: {layout!r}")
            # business_role 语义：仅 prop 可声明，advertised_product 必须独立生成
            role = item.get("business_role")
            if role is not None and group != "props":
                errors.append(f"{group} 资产 {name} 不应声明 business_role: {role!r}")
            if group == "props" and role == "advertised_product":
                if item.get("generation_required") is not True:
                    errors.append(f"广告商品 {name} 必须 generation_required=true 并生成独立参考图")
                if layout not in ALLOWED_REFERENCE_LAYOUTS:
                    errors.append(f"广告商品 {name} 必须使用参考图约定 prop_single_reference_v1")
    for line in warnings:
        print("WARN: " + line)
    for line in errors:
        print("FAIL: " + line)
    if errors:
        raise SystemExit(1)
    print(f"OK: {len(ids)} assets, {len(warnings)} semantic warnings")


if __name__ == "__main__":
    main()
