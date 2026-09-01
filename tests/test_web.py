import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from content_agent.models import CandidateContent
from content_agent.config import AgentConfig
from content_agent.web import (
    SESSION_COOKIE,
    ContentAgentHandler,
    JobStore,
    WebJob,
    WebRunOptions,
    validate_step_prerequisites,
    render_index_html,
    render_landing_html,
    render_owner_auth_html,
    render_trial_html,
    mark_xiaohongshu_published,
    run_agent_step,
    run_agent_workflow,
    submit_stored_previewed_wechat_draft,
    submit_previewed_wechat_draft,
    _options_from_json,
    _options_to_json,
    _asset_rows_from_result,
    _localized_generation_progress,
)


class TwoStageLLMProvider:
    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return next(self.responses)


def _llm_plan_response() -> str:
    return json.dumps(
        {
            "core_topic": "用岗位和组织结构定义可协作的 AI 智能体团队",
            "target_audience": "多智能体开发者和小团队",
            "pain_point": "普通多智能体示例缺少岗位职责和协作边界",
            "core_value": "把岗位职责和协作流程变成可运行的 AI 团队",
            "key_points": ["岗位定义", "组织关系", "交付标准"],
            "article_structure": ["冲突开场", "岗位机制", "协作流程", "真实场景", "边界判断"],
            "cover_concept": "多个具有明确岗位分工的 AI 角色围绕业务目标协作",
            "titles": [
                "Agency Agents：把岗位职责变成一支 AI 团队",
                "多智能体不只会聊天，它把岗位关系也做进去了",
                "想组一支 AI 团队，先给智能体写岗位说明书",
                "把组织架构搬进 AI，多智能体终于有明确分工",
                "AI 团队总抢活？先把每个智能体的岗位定清楚",
            ],
            "selected_title": "Agency Agents：把岗位职责变成一支 AI 团队",
        },
        ensure_ascii=False,
    )


def _agency_candidate() -> CandidateContent:
    return CandidateContent(
        title="GitHub 开源项目：msitarzewski/agency-agents - Agency Agents",
        source="websearch_mcp",
        url="https://github.com/msitarzewski/agency-agents/blob/main/README.md",
        heat=92,
        interaction=88,
        hook=84,
        pain=80,
        reuse=92,
        material=96,
        summary="每个 AI 智能体都有明确岗位职责、组织关系、工作流程和交付标准。",
    )


class WebTests(unittest.TestCase):
    def test_localizes_wechat_rewrite_progress(self):
        events = []

        _localized_generation_progress(events.append)("Rewriting off-topic WeChat draft")

        self.assertEqual(events, ["正在根据主题重新生成公众号正文"])

    def test_index_html_contains_workbench_controls(self):
        html = render_index_html()

        self.assertIn('id="keyword"', html)
        self.assertIn("创作提示词", html)
        self.assertIn("把你想写什么、给谁看、希望什么风格写清楚", html)
        self.assertIn('value="baidu_search"', html)
        self.assertNotIn('value="free_hot"', html)
        self.assertNotIn('value="mock"', html)
        self.assertNotIn('value="public_search"', html)
        self.assertNotIn("public_search API", html)
        self.assertNotIn('id="useLlm"', html)
        self.assertNotIn('id="formatGzh"', html)
        self.assertNotIn('id="generateCover"', html)
        self.assertIn('id="formatTheme"', html)
        self.assertIn('id="coverStyle"', html)
        self.assertNotIn('id="wechatContentHtml"', html)
        self.assertNotIn('id="wechatCoverImage"', html)
        self.assertNotIn("已有公众号 HTML", html)
        self.assertNotIn("已有封面图", html)
        self.assertIn('id="runAllButton"', html)
        self.assertIn('data-step="all"', html)
        self.assertIn("一键生成全部", html)
        self.assertIn('payload.format_gzh = payload.channel === "wechat"', html)
        self.assertIn("正在理解创作提示词、收集素材、生成小红书笔记、封面和图文排版", html)
        self.assertIn("result.llm_drafts && result.llm_drafts.xhs_note", html)
        self.assertIn("aspect-ratio: 16 / 9", html)
        self.assertIn('data-step="materials"', html)
        self.assertIn('data-step="content"', html)
        self.assertIn('data-step="format"', html)
        self.assertIn('data-step="cover"', html)
        self.assertIn('data-step="xhs-layout"', html)
        self.assertIn("图文排版", html)
        self.assertIn('id="xhsLayoutTheme"', html)
        self.assertIn("打包下载全部图片", html)
        self.assertIn("xhs-card-gallery", html)
        self.assertIn("layout.publish_text", html)
        self.assertIn(".panel pre", html)
        self.assertIn("white-space: pre-wrap", html)
        self.assertIn(".cover.xhs-cover", html)
        self.assertIn("aspect-ratio: 3 / 4", html)
        self.assertIn('const coverClass = xhsNote ? "cover xhs-cover" : "cover"', html)
        self.assertNotIn("勾选公众号排版后展示预览", html)
        self.assertNotIn("勾选生成封面", html)
        self.assertIn('id="submitDraftButton"', html)
        self.assertIn('id="xhsPublishedButton"', html)
        self.assertIn("复制发布文案", html)
        self.assertIn("复制标签", html)
        self.assertIn("打开小红书创作平台", html)
        self.assertIn("steps/xhs-published", html)
        self.assertIn('published: "已发布"', html)
        self.assertIn('id="historyList"', html)
        self.assertIn("历史记录", html)
        self.assertIn("loadHistory", html)
        self.assertIn("statusLabels", html)
        self.assertIn("publishLabel", html)
        self.assertIn('href="/settings/wechat"', html)
        self.assertIn("公众号参数", html)
        self.assertIn('href="/auth/wechat-official/start"', html)
        self.assertIn("授权公众号", html)
        self.assertNotIn('id="submitWechatDraft"', html)
        self.assertIn("index === 0 ? renderTitleLab", html)
        self.assertIn('payload.use_llm = true;', html)

    def test_one_click_uses_deepseek_for_plan_then_content(self):
        llm = TwoStageLLMProvider([_llm_plan_response(), "# 临时标题\n\n围绕岗位职责和协作关系展开正文。"])
        config = type("Config", (), {"build_llm_provider": lambda self: llm})()

        with patch("content_agent.web._collect_candidates", return_value=[_agency_candidate()]), patch(
            "content_agent.web.AgentConfig.from_env_file", return_value=config
        ):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="https://github.com/msitarzewski/agency-agents/blob/main/README.md 分享",
                    channel="wechat",
                    use_llm=True,
                    format_gzh=False,
                    generate_cover=False,
                )
            )

        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("请先做内容策划，不要写正文", llm.prompts[0])
        self.assertIn("公众号文案创作", llm.prompts[1])
        self.assertEqual(payload["topics"][0]["optimized_title"], "Agency Agents：把岗位职责变成一支 AI 团队")
        self.assertEqual(payload["content_plan"]["core_value"], "把岗位职责和协作流程变成可运行的 AI 团队")
        self.assertTrue(payload["llm_drafts"]["wechat_article"].startswith("# Agency Agents：把岗位职责变成一支 AI 团队"))
        self.assertIn("明确岗位分工", payload["cover_prompt"])

    def test_materials_step_uses_deepseek_for_title_plan(self):
        llm = TwoStageLLMProvider([_llm_plan_response()])
        config = type("Config", (), {"build_llm_provider": lambda self: llm})()

        with patch("content_agent.web._collect_candidates", return_value=[_agency_candidate()]), patch(
            "content_agent.web.AgentConfig.from_env_file", return_value=config
        ):
            payload = run_agent_step(
                WebRunOptions(
                    keyword="https://github.com/msitarzewski/agency-agents/blob/main/README.md 分享",
                    channel="wechat",
                    use_llm=True,
                ),
                step="materials",
            )

        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("请先做内容策划，不要写正文", llm.prompts[0])
        self.assertEqual(payload["topics"][0]["optimized_title"], "Agency Agents：把岗位职责变成一支 AI 团队")
        self.assertNotIn("llm_drafts", payload)

    def test_run_agent_workflow_exposes_creative_brief_and_title_candidates(self):
        candidate = CandidateContent(
            title="AI副业避坑：这些卖课套路正在收割新人",
            source="baidu_search",
            url="https://example.com/risk",
            heat=86,
            interaction=80,
            hook=84,
            pain=88,
            reuse=80,
            material=76,
        )

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="帮我写公众号，主题是 AI 接单怎么找到第一单，目标读者是新手，要求真实案例和避坑",
                    channel="wechat",
                    collector="baidu_search",
                    format_gzh=False,
                )
            )

        self.assertEqual(payload["creative_brief"]["topic"], "AI 接单怎么找到第一单")
        self.assertGreaterEqual(len(payload["topics"][0]["title_candidates"]), 5)
        self.assertIn("cover_strategy", payload)
        self.assertIn("AI 接单怎么找到第一单", payload["cover_strategy"]["core_message"])

    def test_landing_html_introduces_product_with_platform_neutral_ctas(self):
        html = render_landing_html()

        self.assertIn("Media Agent", html)
        self.assertIn("把自媒体创作从想法推进到可发布", html)
        self.assertIn("自动筛选爆款数据", html)
        self.assertIn("公众号", html)
        self.assertIn("小红书", html)
        self.assertIn("百家号", html)
        self.assertIn('href="/trial"', html)
        self.assertNotIn("微信授权试用", html)
        self.assertNotIn("手动填写公众号参数", html)
        self.assertNotIn('id="runForm"', html)

    def test_trial_html_lists_available_and_coming_platforms(self):
        html = render_trial_html()

        self.assertIn("选择要试用的平台", html)
        self.assertIn("微信公众号", html)
        self.assertIn('href="/auth/wechat/start?next=/app"', html)
        self.assertIn('href="/auth/wechat-official/start"', html)
        self.assertIn('href="/auth/manual"', html)
        self.assertIn('href="/auth/owner"', html)
        self.assertIn("百家号", html)
        self.assertIn("小红书", html)
        self.assertIn("敬请期待", html)

    def test_owner_auth_html_never_contains_server_wechat_credentials(self):
        html = render_owner_auth_html(configured=True)

        self.assertIn("使用服务器账号进入", html)
        self.assertIn('name="password"', html)
        self.assertNotIn("WECHAT_APP_SECRET", html)
        self.assertNotIn("公众号 AppSecret", html)

    def test_owner_auth_html_explains_missing_admin_password(self):
        html = render_owner_auth_html(configured=False)

        self.assertIn("OWNER_LOGIN_PASSWORD", html)
        self.assertNotIn('name="password"', html)

    def test_session_cookie_name_is_stable(self):
        self.assertEqual(SESSION_COOKIE, "media_agent_session")

    def test_index_html_keeps_long_names_readable(self):
        html = render_index_html()

        self.assertIn("Content Agent 内容工作台", html)
        self.assertIn("overflow-wrap: anywhere", html)
        self.assertIn("source-title", html)

    def test_run_agent_workflow_returns_progress_and_payload(self):
        candidate = CandidateContent(
            title="真实热榜里的 AI 副业趋势",
            source="google_news_rss",
            url="https://example.com/topic",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )
        events = []

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=False,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertEqual(payload["keyword"], "AI副业")
        self.assertEqual(payload["topics"][0]["title"], "真实热榜里的 AI 副业趋势")
        self.assertIn("正在用百度搜索收集候选素材", events)
        self.assertIn("正在评分并生成选题", events)

    def test_run_agent_workflow_falls_back_to_keyword_seed_when_baidu_search_is_empty(self):
        events = []

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="codex制作出海网站",
                    channel="wechat",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=False,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertEqual(payload["keyword"], "codex制作出海网站")
        self.assertGreaterEqual(len(payload["topics"]), 1)
        self.assertIn("codex制作出海网站", payload["topics"][0]["title"])
        self.assertEqual(payload["topics"][0]["source"], "keyword_seed")
        self.assertIn("百度搜索暂无结果，已改用关键词种子选题", events)

    def test_run_agent_workflow_can_use_baidu_search_collector(self):
        candidate = CandidateContent(
            title="Codex 制作出海网站的 5 个关键步骤",
            source="baidu_search",
            url="https://example.com/codex-site",
            heat=84,
            interaction=76,
            hook=86,
            pain=80,
            reuse=88,
            material=78,
        )
        events = []

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="codex制作出海网站",
                    channel="wechat",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=False,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertEqual(payload["topics"][0]["source"], "baidu_search")
        self.assertIn("Codex 制作出海网站", payload["topics"][0]["title"])
        self.assertIn("正在用百度搜索收集候选素材", events)

    def test_run_agent_workflow_prefers_websearch_mcp_when_prompt_contains_repo_link(self):
        websearch_candidate = CandidateContent(
            title="GitHub 开源项目：bansen/media-agent - AI content agent",
            source="websearch_mcp",
            url="https://github.com/bansen/media-agent",
            heat=96,
            interaction=90,
            hook=88,
            pain=80,
            reuse=92,
            material=96,
            summary="项目：bansen/media-agent；Stars: 1234；README 摘要：公众号草稿箱工作流。",
        )
        baidu_candidate = CandidateContent(
            title="自媒体 AI 工具合集",
            source="baidu_search",
            url="https://example.com/tools",
            heat=70,
            interaction=65,
            hook=72,
            pain=68,
            reuse=70,
            material=65,
        )
        events = []
        config = AgentConfig(
            llm_provider="deepseek",
            llm_base_url="https://api.deepseek.com",
            llm_model="deepseek-chat",
            llm_api_key="",
            replicate_api_token="",
            replicate_cover_model_version="",
            replicate_cover_model="black-forest-labs/flux-1.1-pro",
            wechat_app_id="",
            wechat_app_secret="",
            wechat_access_token="",
            free_hot_sources=[],
            database_url="",
            baidu_search_api_key="baidu-secret",
            websearch_mcp_enabled=True,
            tavily_api_key="test-tavily-key",
        )

        with patch("content_agent.web.collect_websearch_mcp_candidates", return_value=[websearch_candidate]), patch(
            "content_agent.web.collect_baidu_search_candidates", return_value=[baidu_candidate]
        ), patch(
            "content_agent.web.AgentConfig.from_env_file", return_value=config
        ):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="帮我写公众号，分享这个项目 https://github.com/bansen/media-agent",
                    channel="wechat",
                    collector="baidu_search",
                    format_gzh=False,
                ),
                progress=events.append,
            )

        self.assertEqual(payload["topics"][0]["source"], "websearch_mcp")
        self.assertIn("bansen/media-agent", payload["topics"][0]["source_summary"])
        self.assertIn("正在通过 WebSearch MCP 读取链接内容", events)
        self.assertIn("正在用百度搜索补充外部素材", events)

    def test_run_agent_workflow_reports_missing_tavily_key_before_starting_mcp(self):
        with patch("content_agent.web.AgentConfig.from_env_file") as from_env:
            from_env.return_value = AgentConfig(
                llm_provider="deepseek",
                llm_base_url="https://api.deepseek.com",
                llm_model="deepseek-chat",
                llm_api_key="",
                replicate_api_token="",
                replicate_cover_model_version="",
                replicate_cover_model="black-forest-labs/flux-1.1-pro",
                wechat_app_id="",
                wechat_app_secret="",
                wechat_access_token="",
                free_hot_sources=[],
                database_url="",
                baidu_search_api_key="baidu-secret",
                websearch_mcp_enabled=True,
                tavily_api_key="",
            )

            with self.assertRaisesRegex(RuntimeError, "生产环境缺少 TAVILY_API_KEY"):
                run_agent_workflow(
                    WebRunOptions(
                        keyword="写一篇分享 https://github.com/huangruiteng/loopx/blob/main/README.zh-CN.md 的文章",
                        channel="wechat",
                        collector="baidu_search",
                        format_gzh=False,
                    )
                )

    def test_web_rejects_paid_public_search_collector(self):
        with self.assertRaisesRegex(ValueError, "collector must be baidu_search"):
            run_agent_workflow(WebRunOptions(keyword="AI副业", channel="wechat", collector="public_search"))

    def test_run_agent_workflow_can_format_gzh_preview(self):
        candidate = CandidateContent(
            title="公众号排版测试",
            source="mock",
            url="https://example.com/topic",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )
        events = []

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=True,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertIn("gzh_formatting", payload)
        self.assertIn("正在进行公众号排版", events)

    def test_run_agent_workflow_skips_gzh_format_for_xiaohongshu_channel(self):
        candidate = CandidateContent(
            title="办公室久坐人群，一天 4 个时间点这样调整",
            source="mock",
            url="https://example.com/health",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )
        events = []

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="健康养生",
                    channel="xiaohongshu",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=True,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertNotIn("gzh_formatting", payload)
        self.assertNotIn("正在进行公众号排版", events)

    def test_xiaohongshu_all_workflow_generates_three_to_four_cover_and_layout(self):
        candidate = CandidateContent(
            title="办公室久坐人群，一天 4 个时间点这样调整",
            source="baidu_search",
            url="https://example.com/health",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )
        config = AgentConfig(
            llm_provider="deepseek",
            llm_base_url="https://api.deepseek.com",
            llm_model="deepseek-chat",
            llm_api_key="secret",
            replicate_api_token="replicate-secret",
            replicate_cover_model_version="",
            replicate_cover_model="black-forest-labs/flux-1.1-pro",
            wechat_app_id="",
            wechat_app_secret="",
            wechat_access_token="",
            free_hot_sources=[],
            database_url="",
            baidu_search_api_key="baidu-secret",
        )
        generated_cover = type(
            "Cover",
            (),
            {"path": Path("output/xhs-cover.jpg"), "url": "", "model": "flux", "prompt": "prompt"},
        )()
        package = type(
            "Package",
            (),
            {"to_dict": lambda self: {"theme": "fresh-green", "cards": [{"path": "output/01-cover.jpg"}], "zip_path": "output/package.zip"}},
        )()

        with patch("content_agent.web.AgentConfig.from_env_file", return_value=config), patch(
            "content_agent.web.collect_baidu_search_candidates", return_value=[candidate]
        ), patch(
            "content_agent.web.generate_llm_content_plan", return_value=object()
        ), patch(
            "content_agent.web.apply_llm_content_plan", side_effect=lambda result, plan, channel: result
        ), patch(
            "content_agent.web.generate_llm_drafts",
            return_value={"xhs_note": "标题：久坐女性的4个习惯\n\n正文：\n\n1. 喝水\n慢慢喝。\n\n标签：#健康养生"},
        ), patch("content_agent.web.generate_cover_image", return_value=generated_cover) as cover, patch(
            "content_agent.web.render_xhs_package", return_value=package
        ) as layout:
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="健康养生",
                    channel="xiaohongshu",
                    use_llm=True,
                    generate_cover=True,
                    xhs_layout_theme="auto",
                )
            )

        self.assertEqual(cover.call_args.kwargs["aspect_ratio"], "3:4")
        self.assertEqual(layout.call_args.kwargs["background_path"], "output/xhs-cover.jpg")
        self.assertIn("xhs_layout", payload)

    def test_web_run_options_persist_format_and_cover_styles(self):
        options = WebRunOptions(
            keyword="AI副业",
            format_theme="tech-blue",
            cover_style="real-photo",
            xhs_layout_theme="warm-coral",
        )

        stored = _options_from_json(_options_to_json(options))

        self.assertEqual(stored.format_theme, "tech-blue")
        self.assertEqual(stored.cover_style, "real-photo")
        self.assertEqual(stored.xhs_layout_theme, "warm-coral")

    def test_run_agent_workflow_applies_selected_cover_style_once(self):
        candidate = CandidateContent(
            title="AI副业真实案例",
            source="baidu_search",
            url="https://example.com/topic",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="baidu_search",
                    cover_style="real-photo",
                    format_gzh=False,
                )
            )

        self.assertIn("realistic lifestyle photography", payload["cover_prompt"])
        self.assertNotIn("business technology editorial photo", payload["cover_prompt"])

    def test_run_agent_workflow_keeps_github_cover_subject_when_style_changes(self):
        candidate = CandidateContent(
            title="GitHub 开源项目：huangruiteng/loopx - 项目资料",
            source="baidu_search",
            url="https://github.com/huangruiteng/loopx",
            heat=92,
            interaction=88,
            hook=84,
            pain=80,
            reuse=92,
            material=96,
            summary="LoopX 给现有 Agent 补上一层长期工作控制系统。",
        )

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="写一篇分享 LoopX 开源项目的文章",
                    channel="wechat",
                    collector="baidu_search",
                    cover_style="real-photo",
                    format_gzh=False,
                )
            )

        prompt = payload["cover_prompt"].lower()
        self.assertIn("open-source agent system", prompt)
        self.assertIn("realistic cinematic product visualization", prompt)
        self.assertNotIn("realistic lifestyle photography", prompt)
        self.assertNotIn("office desk", prompt)

    def test_step_prerequisites_block_missing_previous_steps(self):
        with self.assertRaisesRegex(ValueError, "请先搜素材"):
            validate_step_prerequisites("content", None)
        with self.assertRaisesRegex(ValueError, "请先生成内容"):
            validate_step_prerequisites("format", {"topics": [{}]})
        with self.assertRaisesRegex(ValueError, "请先生成封面"):
            validate_step_prerequisites(
                "submit",
                {"topics": [{}], "gzh_formatting": {"clean_html": "output/a.html"}},
            )
        with self.assertRaisesRegex(ValueError, "请先生成小红书内容"):
            validate_step_prerequisites("xhs-layout", {"topics": [{}]})

    def test_xiaohongshu_layout_step_uses_note_and_cover_background(self):
        current = {
            "topics": [{"title": "秋季养生"}],
            "llm_drafts": {"xhs_note": "标题：秋天养元气\n\n正文：\n\n1. 早起喝水\n慢慢喝。\n\n标签：#健康养生"},
            "cover_image": {"path": "output/background.jpg"},
        }
        package = type("Package", (), {"to_dict": lambda self: {"theme": "fresh-green", "cards": [], "zip_path": "output/package.zip"}})()

        with patch("content_agent.web.render_xhs_package", return_value=package) as render:
            payload = run_agent_step(
                WebRunOptions(keyword="秋季养生", channel="xiaohongshu", xhs_layout_theme="fresh-green"),
                step="xhs-layout",
                current_result=current,
                package_id="job-layout",
            )

        self.assertEqual(payload["xhs_layout"]["theme"], "fresh-green")
        self.assertEqual(render.call_args.kwargs["background_path"], "output/background.jpg")
        self.assertEqual(render.call_args.kwargs["package_id"], "job-layout")

    def test_regenerating_xiaohongshu_content_discards_old_layout(self):
        current = {
            "keyword": "秋季养生",
            "expanded_keywords": ["秋季养生"],
            "topics": [{"title": "秋季养生"}],
            "wechat_outline": "",
            "xhs_package": "",
            "cover_prompt": "cover prompt",
            "content_plan": {"core_topic": "秋季养生"},
            "xhs_layout": {"cards": [{"path": "output/old.jpg"}], "zip_path": "output/old.zip"},
        }

        with patch("content_agent.web.AgentConfig.from_env_file") as config:
            config.return_value.build_llm_provider.return_value = object()
            with patch("content_agent.web.generate_llm_drafts", return_value={"xhs_note": "标题：新内容"}):
                payload = run_agent_step(
                    WebRunOptions(keyword="秋季养生", channel="xiaohongshu"),
                    step="content",
                    current_result=current,
                )

        self.assertNotIn("xhs_layout", payload)

    def test_regenerating_xiaohongshu_cover_discards_old_layout(self):
        current = {
            "topics": [{"title": "秋季养生"}],
            "cover_prompt": "cover prompt",
            "llm_drafts": {"xhs_note": "标题：秋季养生"},
            "xhs_layout": {"cards": [{"path": "output/old.jpg"}], "zip_path": "output/old.zip"},
        }
        generated = type("Cover", (), {"path": Path("output/new.jpg"), "url": "", "model": "mock", "prompt": "cover prompt"})()

        with patch("content_agent.web.AgentConfig.from_env_file") as config:
            config.return_value.replicate_cover_model = "mock"
            config.return_value.replicate_api_token = "token"
            with patch("content_agent.web.generate_cover_image", return_value=generated):
                payload = run_agent_step(
                    WebRunOptions(keyword="秋季养生", channel="xiaohongshu"),
                    step="cover",
                    current_result=current,
                )

        self.assertNotIn("xhs_layout", payload)

    def test_switching_channel_then_regenerating_content_discards_old_xhs_layout(self):
        current = {
            "keyword": "秋季养生",
            "expanded_keywords": ["秋季养生"],
            "topics": [{"title": "秋季养生"}],
            "wechat_outline": "",
            "xhs_package": "",
            "cover_prompt": "cover prompt",
            "content_plan": {"core_topic": "秋季养生"},
            "xhs_layout": {"cards": [{"path": "output/old.jpg"}], "zip_path": "output/old.zip"},
        }

        with patch("content_agent.web.AgentConfig.from_env_file") as config:
            config.return_value.build_llm_provider.return_value = object()
            with patch("content_agent.web.generate_llm_drafts", return_value={"wechat_article": "# 新内容"}):
                payload = run_agent_step(
                    WebRunOptions(keyword="秋季养生", channel="wechat"),
                    step="content",
                    current_result=current,
                )

        self.assertNotIn("xhs_layout", payload)

    def test_switching_channel_then_regenerating_cover_discards_old_xhs_layout(self):
        current = {
            "topics": [{"title": "秋季养生"}],
            "cover_prompt": "cover prompt",
            "xhs_layout": {"cards": [{"path": "output/old.jpg"}], "zip_path": "output/old.zip"},
        }
        generated = type("Cover", (), {"path": Path("output/new.jpg"), "url": "", "model": "mock", "prompt": "cover prompt"})()

        with patch("content_agent.web.AgentConfig.from_env_file") as config:
            config.return_value.replicate_cover_model = "mock"
            config.return_value.replicate_api_token = "token"
            with patch("content_agent.web.generate_cover_image", return_value=generated):
                payload = run_agent_step(
                    WebRunOptions(keyword="秋季养生", channel="wechat"),
                    step="cover",
                    current_result=current,
                )

        self.assertNotIn("xhs_layout", payload)

    def test_job_store_passes_job_id_to_asset_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}", auto_start=False)
            job = store.create(WebRunOptions(keyword="秋季养生", channel="xiaohongshu"), user_id=1)

            with patch("content_agent.web.run_agent_workflow", return_value={"topics": []}) as workflow:
                store._run_job(job.id)

            self.assertEqual(workflow.call_args.kwargs["package_id"], job.id)

    def test_xiaohongshu_assets_are_persisted_for_authenticated_downloads(self):
        result = {
            "xhs_layout": {
                "theme": "fresh-green",
                "cards": [
                    {"index": 1, "kind": "cover", "path": "output/xhs/01-cover.jpg", "title": "标题"},
                    {"index": 2, "kind": "tail", "path": "output/xhs/02-tail.jpg", "title": "结尾"},
                ],
                "zip_path": "output/xhs/xiaohongshu-package.zip",
            }
        }

        rows = _asset_rows_from_result("job1", result, created_at=1.0)

        self.assertEqual([row.kind for row in rows], ["xiaohongshu_card", "xiaohongshu_card", "xiaohongshu_package"])
        self.assertEqual(rows[-1].mime_type, "application/zip")

    def test_run_agent_workflow_exposes_existing_cover_for_preview_submit(self):
        candidate = CandidateContent(
            title="已有封面图测试",
            source="mock",
            url="https://example.com/topic",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=False,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    wechat_cover_image="output/manual-cover.jpg",
                    output_dir=Path("output"),
                )
            )

        self.assertEqual(payload["cover_image"]["path"], "output/manual-cover.jpg")
        self.assertEqual(payload["cover_image"]["model"], "manual")

    def test_mark_xiaohongshu_published_records_manual_publish_attempt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}", auto_start=False)
            job = store.create(
                WebRunOptions(keyword="健康养生", channel="xiaohongshu", collector="baidu_search"),
                user_id=1,
            )
            package_path = Path(tmpdir) / "xiaohongshu-package.zip"
            package_path.write_bytes(b"zip")
            store._update(
                job.id,
                result={
                    "keyword": "健康养生",
                    "expanded_keywords": ["健康养生"],
                    "topics": [],
                    "wechat_outline": "",
                    "xhs_package": "",
                    "cover_prompt": "",
                    "llm_drafts": {"xhs_note": "标题：久坐人群可收藏的习惯清单\n\n标签：#健康养生"},
                    "xhs_layout": {
                        "cards": [{"path": str(Path(tmpdir) / "01-cover.jpg")}],
                        "zip_path": str(package_path),
                    },
                },
            )

            marked = mark_xiaohongshu_published(store, job.id)

            self.assertEqual(marked.status, "published")
            self.assertEqual(marked.publish_attempts[-1]["platform"], "xiaohongshu")
            self.assertEqual(marked.publish_attempts[-1]["status"], "published")
            self.assertIn("小红书已标记为人工发布", marked.events)

    def test_mark_xiaohongshu_published_requires_complete_layout_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}", auto_start=False)
            job = store.create(WebRunOptions(keyword="健康养生", channel="xiaohongshu"), user_id=1)
            store._update(job.id, result={"llm_drafts": {"xhs_note": "标题：健康养生"}})

            with self.assertRaisesRegex(ValueError, "请先生成小红书图文排版"):
                mark_xiaohongshu_published(store, job.id)

    def test_submit_previewed_wechat_draft_uses_existing_preview_and_cover(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clean_html = Path(tmpdir) / "preview.html"
            clean_html.write_text("<p>已预览内容</p>", encoding="utf-8")
            cover_image = Path(tmpdir) / "cover.jpg"
            cover_image.write_bytes(b"fake-image")
            job = WebJob(
                id="job1",
                options=WebRunOptions(keyword="AI副业"),
                status="completed",
                result={
                    "keyword": "AI副业",
                    "expanded_keywords": ["AI副业"],
                    "topics": [
                        {
                            "title": "来源标题",
                            "optimized_title": "普通人做 AI 副业，先看懂这 3 个真实信号",
                            "score": {"total": 81.1, "level": "A", "reasons": []},
                            "source": "mock",
                            "url": "https://example.com/topic",
                            "platform_fit": ["wechat"],
                            "angle": "普通人视角",
                            "material_needs": ["案例"],
                            "risk_notes": ["避免承诺收益"],
                        }
                    ],
                    "wechat_outline": "公众号文章：《普通人做 AI 副业，先看懂这 3 个真实信号》",
                    "xhs_package": "小红书标题：普通人做 AI 副业，先看懂这 3 个真实信号",
                    "cover_prompt": "Replicate image prompt",
                    "gzh_formatting": {"clean_html": str(clean_html), "preview_html": str(clean_html)},
                    "cover_image": {"path": str(cover_image), "url": "", "model": "mock", "prompt": "mock"},
                },
            )
            events = []

            with patch("content_agent.web.AgentConfig.from_env_file", return_value=object()), patch(
                "content_agent.web.publish_wechat_draft"
            ) as publish:
                publish.return_value.thumb_media_id = "MEDIA_ID"
                publish.return_value.response = {"errcode": 0, "media_id": "DRAFT_ID"}

                result = submit_previewed_wechat_draft(job, progress=events.append)

        self.assertEqual(result["wechat_draft"]["thumb_media_id"], "MEDIA_ID")
        self.assertIn("正在从预览提交公众号草稿箱", events)
        self.assertEqual(publish.call_args.kwargs["content_html"], "<p>已预览内容</p>")
        self.assertEqual(publish.call_args.kwargs["cover_image_path"], str(cover_image))

    def test_submit_previewed_wechat_draft_requires_completed_preview(self):
        job = WebJob(
            id="job1",
            options=WebRunOptions(keyword="AI副业"),
            status="running",
            result=None,
        )

        with self.assertRaisesRegex(ValueError, "completed preview"):
            submit_previewed_wechat_draft(job)

    def test_submit_stored_previewed_wechat_draft_uses_snapshot_before_publishing_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}", auto_start=False)
            clean_html = Path(tmpdir) / "preview.html"
            clean_html.write_text("<p>已预览内容</p>", encoding="utf-8")
            cover_image = Path(tmpdir) / "cover.jpg"
            cover_image.write_bytes(b"fake-image")
            job = store.create(WebRunOptions(keyword="AI副业"), user_id=1)
            result_payload = {
                "keyword": "AI副业",
                "expanded_keywords": ["AI副业"],
                "topics": [
                    {
                        "title": "来源标题",
                        "optimized_title": "普通人做 AI 副业，先看懂这 3 个真实信号",
                        "score": {"total": 81.1, "level": "A", "reasons": []},
                        "source": "baidu_search",
                        "url": "https://example.com/topic",
                        "platform_fit": ["wechat"],
                        "angle": "普通人视角",
                        "material_needs": ["案例"],
                        "risk_notes": ["避免承诺收益"],
                    }
                ],
                "wechat_outline": "公众号文章：《普通人做 AI 副业，先看懂这 3 个真实信号》",
                "xhs_package": "小红书标题：普通人做 AI 副业，先看懂这 3 个真实信号",
                "cover_prompt": "Replicate image prompt",
                "gzh_formatting": {"clean_html": str(clean_html), "preview_html": str(clean_html)},
                "cover_image": {"path": str(cover_image), "url": "", "model": "mock", "prompt": "mock"},
            }
            store._update(job.id, status="preview_ready", result=result_payload, event="Job completed")

            with patch("content_agent.web.publish_wechat_draft") as publish:
                publish.return_value.thumb_media_id = "MEDIA_ID"
                publish.return_value.response = {"errcode": 0, "media_id": "DRAFT_ID"}
                submitted = submit_stored_previewed_wechat_draft(store, job.id, config=object())

        self.assertEqual(submitted.status, "published_draft")
        self.assertEqual(submitted.result["wechat_draft"]["thumb_media_id"], "MEDIA_ID")
        self.assertIn("开始提交草稿箱", submitted.events)
        self.assertIn("草稿箱提交完成", submitted.events)

    def test_wechat_publish_config_prefers_component_authorized_account(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}", auto_start=False)
            user = store.auth.upsert_external_user(provider="wechat", provider_user_id="openid-1", display_name="用户")
            store.auth.update_manual_wechat_account(
                user_id=user.id,
                display_name="手动公众号",
                app_id="wx-manual",
                app_secret="manual-secret",
                access_token="manual-token",
            )
            store.auth.upsert_component_wechat_account(
                user_id=user.id,
                authorizer_appid="wx-authorizer",
                display_name="授权公众号",
                authorizer_refresh_token="refresh-token",
                authorizer_access_token="component-token",
                expires_in=7200,
                profile={},
            )
            handler = object.__new__(ContentAgentHandler)
            handler.store = store
            base_config = AgentConfig(
                llm_provider="deepseek",
                llm_base_url="https://api.deepseek.com",
                llm_model="deepseek-chat",
                llm_api_key="secret",
                replicate_api_token="replicate-secret",
                replicate_cover_model_version="",
                replicate_cover_model="black-forest-labs/flux-1.1-pro",
                wechat_app_id="env-app",
                wechat_app_secret="env-secret",
                wechat_access_token="",
                free_hot_sources=["google_news_rss"],
                database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}",
            )

            with patch("content_agent.web.AgentConfig.from_env_file", return_value=base_config):
                publish_config = handler._wechat_publish_config_for_user(user.id)

        self.assertEqual(publish_config.wechat_app_id, "wx-authorizer")
        self.assertEqual(publish_config.wechat_app_secret, "")
        self.assertEqual(publish_config.wechat_access_token, "component-token")


if __name__ == "__main__":
    unittest.main()
