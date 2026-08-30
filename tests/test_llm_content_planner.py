import json
import unittest

from content_agent.llm_content_planner import apply_llm_content_plan, generate_llm_content_plan
from content_agent.models import CandidateContent
from content_agent.workflow import run_keyword_workflow


class FakeLLMProvider:
    def __init__(self, response: str):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class SequenceLLMProvider:
    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return next(self.responses)


def _response(selected_title: str = "Agency Agents：把岗位职责变成一支 AI 团队") -> str:
    payload = {
        "core_topic": "用岗位和组织结构定义可协作的 AI 智能体团队",
        "target_audience": "希望用多智能体处理真实业务流程的开发者和小团队",
        "pain_point": "普通多智能体示例只有对话，没有清晰岗位职责和协作边界",
        "core_value": "把岗位职责、汇报关系和协作流程变成可运行的 AI 团队",
        "key_points": ["用岗位定义智能体", "按组织关系协作", "适合真实业务流程"],
        "article_structure": ["痛点开场", "项目定位", "核心机制", "真实场景", "使用边界"],
        "cover_concept": "多个具有明确岗位分工的 AI 角色围绕同一业务目标协作",
        "titles": [
            selected_title,
            "多智能体不只会聊天，它把岗位和汇报关系也做进去了",
            "想组一支 AI 团队，先给每个智能体一份岗位说明书",
            "把公司组织架构搬进 AI，多智能体终于有了明确分工",
            "AI 团队总在互相抢活？这个项目先把岗位边界定清楚",
        ],
        "selected_title": selected_title,
    }
    return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"


def _workflow_result():
    return run_keyword_workflow(
        "https://github.com/msitarzewski/agency-agents/blob/main/README.md 分享",
        candidates=[
            CandidateContent(
                title="GitHub 开源项目：msitarzewski/agency-agents - Agency Agents",
                source="websearch_mcp",
                url="https://github.com/msitarzewski/agency-agents/blob/main/README.md",
                heat=92,
                interaction=88,
                hook=84,
                pain=80,
                reuse=92,
                material=96,
                summary=(
                    "Agency Agents 提供一套完整的专业 AI 智能体角色，覆盖工程、设计、营销、销售和管理。"
                    "每个角色都有明确职责、工作流程和交付标准，可按组织关系组成协作团队。"
                ),
            )
        ],
    )


class LLMContentPlannerTests(unittest.TestCase):
    def test_generates_grounded_chinese_editorial_plan_from_source(self):
        result = _workflow_result()
        llm = FakeLLMProvider(_response())

        plan = generate_llm_content_plan(llm, result, channel="wechat")

        self.assertEqual(plan.selected_title, "Agency Agents：把岗位职责变成一支 AI 团队")
        self.assertEqual(len(plan.titles), 5)
        self.assertIn("Agency Agents 提供一套完整的专业 AI 智能体角色", llm.prompts[0])
        self.assertIn("只根据用户提示词和素材事实", llm.prompts[0])
        self.assertIn("所有标题必须使用中文表达", llm.prompts[0])
        self.assertIn("只输出 JSON", llm.prompts[0])

    def test_rejects_template_title_even_when_json_is_valid(self):
        result = _workflow_result()
        bad_title = "Agency Agents 值不值得试？先看核心场景和使用门槛"
        llm = FakeLLMProvider(_response(bad_title))

        with self.assertRaisesRegex(ValueError, "模板化禁用词"):
            generate_llm_content_plan(llm, result, channel="wechat")

    def test_retries_once_when_first_plan_has_template_title(self):
        result = _workflow_result()
        bad_title = "Agency Agents 值不值得试？先看核心场景和使用门槛"
        llm = SequenceLLMProvider([_response(bad_title), _response()])

        plan = generate_llm_content_plan(llm, result, channel="wechat")

        self.assertEqual(plan.selected_title, "Agency Agents：把岗位职责变成一支 AI 团队")
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("模板化禁用词", llm.prompts[1])
        self.assertIn("重新输出完整 JSON", llm.prompts[1])

    def test_discards_overlong_selected_title_when_valid_candidates_exist(self):
        result = _workflow_result()
        overlong_title = "在 Codex 里用云端 GPU 生成 MiniMax H3 视频，自动关机省成本"
        llm = FakeLLMProvider(_response(overlong_title))

        plan = generate_llm_content_plan(llm, result, channel="wechat")

        self.assertEqual(plan.selected_title, "多智能体不只会聊天，它把岗位和汇报关系也做进去了")
        self.assertNotIn(overlong_title, plan.titles)
        self.assertEqual(len(llm.prompts), 1)

    def test_applies_llm_title_and_plan_to_outline_and_cover(self):
        result = _workflow_result()
        plan = generate_llm_content_plan(FakeLLMProvider(_response()), result, channel="wechat")

        updated = apply_llm_content_plan(result, plan, channel="wechat")

        self.assertEqual(updated.topics[0].optimized_title, plan.selected_title)
        self.assertEqual(updated.content_plan["core_value"], plan.core_value)
        self.assertEqual(updated.topics[0].title_candidates[0]["title"], plan.selected_title)
        self.assertIn(plan.selected_title, updated.wechat_outline)
        self.assertIn(plan.selected_title, updated.cover_prompt)
        self.assertIn(plan.cover_concept, updated.cover_prompt)


if __name__ == "__main__":
    unittest.main()
