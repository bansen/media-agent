import unittest

from content_agent.models import CandidateContent
from content_agent.workflow import run_keyword_workflow


class TitleOptimizerTests(unittest.TestCase):
    def test_wechat_ai_side_hustle_title_is_optimized_for_attention(self):
        candidates = [
            CandidateContent(
                title="上半年AI服务交易迎爆发式增长 年轻人开始用AI轻创业丨封面有数 - 封面新闻",
                source="google_news_rss",
                url="https://example.com/topic",
                heat=90,
                interaction=84,
                hook=78,
                pain=80,
                reuse=77,
                material=76,
            )
        ]

        result = run_keyword_workflow("AI副业", candidates=candidates, primary_channel="wechat")
        optimized_title = result.topics[0].optimized_title

        self.assertEqual(result.topics[0].title, "上半年AI服务交易迎爆发式增长 年轻人开始用AI轻创业丨封面有数 - 封面新闻")
        self.assertIn("AI", optimized_title)
        self.assertTrue(any(term in optimized_title for term in ["第一单", "切入", "机会", "服务"]))
        self.assertNotEqual(optimized_title, "普通人做 AI 副业，先看懂这 3 个真实信号")
        self.assertIn(f"公众号文章：《{optimized_title}》", result.wechat_outline)
        self.assertIn(f"Main idea: {optimized_title}.", result.cover_prompt)
        self.assertNotIn("封面新闻", optimized_title)
        self.assertNotIn("暴富", optimized_title)
        self.assertNotIn("稳赚", optimized_title)
        self.assertNotIn("月入", optimized_title)
        self.assertNotIn("躺赚", optimized_title)

    def test_wechat_ai_titles_vary_by_topic_angle(self):
        candidates = [
            CandidateContent(
                title="AI副业避坑：这些卖课套路正在收割新人",
                source="baidu_search",
                url="https://example.com/risk",
                heat=90,
                interaction=84,
                hook=88,
                pain=86,
                reuse=77,
                material=76,
            ),
            CandidateContent(
                title="普通人学AI工具的完整路线和提示词教程",
                source="baidu_search",
                url="https://example.com/tool",
                heat=86,
                interaction=80,
                hook=82,
                pain=78,
                reuse=84,
                material=80,
            ),
        ]

        risk = run_keyword_workflow("AI副业", candidates=[candidates[0]], primary_channel="wechat").topics[0].optimized_title
        tool = run_keyword_workflow("AI学习", candidates=[candidates[1]], primary_channel="wechat").topics[0].optimized_title

        self.assertNotEqual(risk, tool)
        self.assertIn("坑", risk)
        self.assertTrue(any(term in tool for term in ["工具", "场景", "路线"]))

    def test_xiaohongshu_health_title_keeps_lifestyle_positioning(self):
        candidates = [
            CandidateContent(
                title="办公室久坐人群，一天 4 个时间点这样调整 - 健康时报",
                source="google_news_rss",
                url="https://example.com/health",
                heat=78,
                interaction=80,
                hook=84,
                pain=88,
                reuse=90,
                material=72,
            )
        ]

        result = run_keyword_workflow("养生", candidates=candidates, primary_channel="xiaohongshu")
        optimized_title = result.topics[0].optimized_title

        self.assertEqual(optimized_title, "久坐职场女性可收藏的 4 个低成本习惯")
        self.assertIn(f"小红书标题：{optimized_title}", result.xhs_package)
        self.assertNotIn("治疗", optimized_title)
        self.assertNotIn("诊断", optimized_title)

    def test_wechat_non_ai_keyword_keeps_keyword_context(self):
        candidates = [
            CandidateContent(
                title="GitHub 项目：fighting41love/funNLP",
                source="github",
                url="https://example.com/funnlp",
                heat=92,
                interaction=88,
                hook=74,
                pain=65,
                reuse=84,
                material=80,
            ),
            CandidateContent(
                title="[云框架]SMACK大数据架构 / [Cloudframeworks]SMACK big data architecture",
                source="hn_algolia",
                url="https://example.com/big-data",
                heat=70,
                interaction=68,
                hook=72,
                pain=76,
                reuse=80,
                material=78,
            ),
        ]

        result = run_keyword_workflow("大数据架构", candidates=candidates, primary_channel="wechat")
        optimized_title = result.topics[0].optimized_title

        self.assertEqual(result.topics[0].title, "[云框架]SMACK大数据架构 / [Cloudframeworks]SMACK big data architecture")
        self.assertIn("大数据架构", optimized_title)
        self.assertNotIn("普通人学 AI", optimized_title)
        self.assertIn(f"公众号文章：《{optimized_title}》", result.wechat_outline)

    def test_wechat_model_release_keyword_uses_source_entity_not_raw_search_phrase(self):
        candidates = [
            CandidateContent(
                title="MiniMax H3正式发布",
                source="baidu_search",
                url="https://example.com/minimax-h3",
                heat=72,
                interaction=70,
                hook=82,
                pain=76,
                reuse=80,
                material=78,
            )
        ]

        result = run_keyword_workflow("minimax h3介绍", candidates=candidates, primary_channel="wechat")
        optimized_title = result.topics[0].optimized_title

        self.assertIn("MiniMax H3", optimized_title)
        self.assertNotIn("minimax h3介绍", optimized_title)
        self.assertTrue(any(term in optimized_title for term in ["发布", "变化", "看懂"]))

    def test_wechat_title_summarizes_descriptive_keyword_instead_of_copying_it(self):
        candidates = [
            CandidateContent(
                title="MiniMax H3官网入口分享:AI视频生成工具到底好不好用?",
                source="baidu_search",
                url="https://example.com/minimax-h3-video",
                heat=75,
                interaction=70,
                hook=82,
                pain=78,
                reuse=80,
                material=78,
            )
        ]

        result = run_keyword_workflow(
            "minimax h3介绍，要突出核心能力（如视频相关等）",
            candidates=candidates,
            primary_channel="wechat",
        )
        optimized_title = result.topics[0].optimized_title

        self.assertIn("MiniMax H3", optimized_title)
        self.assertIn("视频", optimized_title)
        self.assertNotIn("介绍", optimized_title)
        self.assertNotIn("要突出", optimized_title)
        self.assertNotIn("如视频相关等", optimized_title)
        self.assertLessEqual(len(optimized_title), 28)

    def test_github_presentation_tool_title_uses_readme_problem_and_outcome(self):
        result = run_keyword_workflow(
            "https://github.com/chuspeeism/dashi-ppt-skill/blob/main/README.md 项目分享",
            candidates=[
                CandidateContent(
                    title="GitHub 开源项目：chuspeeism/dashi-ppt-skill - dashi-ppt-skill",
                    source="websearch_mcp",
                    url="https://github.com/chuspeeism/dashi-ppt-skill/blob/main/README.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary=(
                        "一个真正适合职场人的 PPT Skill。把文档丢给 AI Agent，"
                        "每一页都自带编辑控制台，不满意的地方可以直接在浏览器里改，"
                        "还能一键导出成真实、可编辑的 PPTX。支持 Claude Code、Codex 等 Agent。"
                    ),
                )
            ],
            primary_channel="wechat",
        )

        optimized_title = result.topics[0].optimized_title
        self.assertIn("PPT", optimized_title)
        self.assertTrue(any(term in optimized_title for term in ["能改", "可编辑", "导出", "PPTX", "交付"]))
        self.assertNotIn("Agent 总是跑偏", optimized_title)
        self.assertNotIn("工作系统", optimized_title)
        self.assertNotIn("github.com", optimized_title)

    def test_github_project_prompt_uses_hook_title_without_exposing_url(self):
        candidates = [
            CandidateContent(
                title="GitHub 开源项目：huangruiteng/loopx - 项目资料",
                source="websearch_mcp",
                url="https://github.com/huangruiteng/loopx/blob/main/README.zh-CN.md",
                heat=92,
                interaction=88,
                hook=84,
                pain=80,
                reuse=92,
                material=96,
                summary="LoopX 给现有 Agent 补上一层长期工作控制系统，让 Codex、Claude Code 这类 Agent 更接近真正的数字员工。",
            )
        ]

        result = run_keyword_workflow(
            "写一篇分享 https://github.com/huangruiteng/loopx/blob/main/README.zh-CN.md 的文章",
            candidates=candidates,
            primary_channel="wechat",
        )
        optimized_title = result.topics[0].optimized_title

        self.assertIn("LoopX", optimized_title)
        self.assertIn("Agent", optimized_title)
        self.assertNotIn("http", optimized_title)
        self.assertNotIn("github.com", optimized_title)
        self.assertNotIn("huangruiteng/loopx", optimized_title)

    def test_github_harness_title_names_project_without_repeating_generic_label(self):
        result = run_keyword_workflow(
            "https://github.com/deepseek-ai/deepseek-harness/blob/master/README.zh.md 推荐一下 deepseek harness",
            candidates=[
                CandidateContent(
                    title="GitHub 开源项目：deepseek-ai/deepseek-harness - 项目资料",
                    source="websearch_mcp",
                    url="https://github.com/deepseek-ai/deepseek-harness/blob/master/README.zh.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary=(
                        "DeepSeek Harness 是由 DeepSeek 开发的开源 Agent Harness，"
                        "采用一切皆插件的架构，目前处于开发者预览阶段。"
                    ),
                )
            ],
            primary_channel="wechat",
        )

        optimized_title = result.topics[0].optimized_title
        self.assertIn("DeepSeek Harness", optimized_title)
        self.assertIn("Agent", optimized_title)
        self.assertIn("插件", optimized_title)
        self.assertLessEqual(optimized_title.count("开源项目"), 1)
        self.assertNotIn("http", optimized_title)
        self.assertNotIn("github.com", optimized_title)

    def test_github_video_creator_title_uses_project_outcome_not_agent_template(self):
        result = run_keyword_workflow(
            "https://github.com/harry0703/MoneyPrinterTurbo/blob/main/README.md 项目分享",
            candidates=[
                CandidateContent(
                    title="GitHub 开源项目：harry0703/MoneyPrinterTurbo - MoneyPrinterTurbo",
                    source="websearch_mcp",
                    url="https://github.com/harry0703/MoneyPrinterTurbo/blob/main/README.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary=(
                        "MoneyPrinterTurbo 是一站式 AI 短视频生成工具。输入主题或关键词，"
                        "自动生成视频脚本、匹配素材、生成字幕和背景音乐，并合成高清短视频。"
                    ),
                )
            ],
            primary_channel="wechat",
        )

        optimized_title = result.topics[0].optimized_title
        self.assertIn("MoneyPrinterTurbo", optimized_title)
        self.assertIn("短视频", optimized_title)
        self.assertIn("不会剪视频", optimized_title)
        self.assertNotIn("项目分享", optimized_title)
        self.assertNotIn("Agent", optimized_title)
        self.assertNotIn("真实问题", optimized_title)

    def test_github_creatorhub_title_uses_readme_content_outcome(self):
        result = run_keyword_workflow(
            "https://github.com/3441293738/creatorhub/blob/main/README.md 项目分享",
            candidates=[
                CandidateContent(
                    title="GitHub 开源项目：3441293738/creatorhub - CreatorHub",
                    source="websearch_mcp",
                    url="https://github.com/3441293738/creatorhub/blob/main/README.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary=(
                        "CreatorHub 是本地运行的多平台内容管理面板，支持抖音、小红书、快手、视频号。"
                        "它用 Python + FastAPI 提供统一 Web 界面，用于管理账号、监控作品与评论、"
                        "下载内容、发布作品和接收通知。"
                    ),
                )
            ],
            primary_channel="wechat",
        )

        optimized_title = result.topics[0].optimized_title
        self.assertEqual(
            optimized_title,
            "多平台运营太分散？CreatorHub 把监控、下载、发布收进一处",
        )
        self.assertNotIn("真实问题", optimized_title)
        self.assertNotIn("项目分享", optimized_title)
        self.assertNotIn("github.com", optimized_title)
        self.assertIn("多平台内容运营工具解读", result.topics[0].angle)
        self.assertIn("作品监控", result.topics[0].angle)


if __name__ == "__main__":
    unittest.main()
