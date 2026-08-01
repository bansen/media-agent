import tempfile
import unittest
from pathlib import Path
from urllib import parse

from content_agent.auth import AuthStore, WeChatLoginConfig, WeChatOAuthProvider
from content_agent.database import build_engine, init_schema, session_factory


class AuthTests(unittest.TestCase):
    def test_wechat_oauth_provider_builds_qrconnect_url(self):
        provider = WeChatOAuthProvider(
            WeChatLoginConfig(
                app_id="wx-app",
                app_secret="secret",
                redirect_uri="https://media-agent.createbeauty.top/auth/wechat/callback",
            )
        )

        url = provider.authorization_url(state="STATE123")
        parsed = parse.urlparse(url)
        params = parse.parse_qs(parsed.query)

        self.assertEqual(parsed.netloc, "open.weixin.qq.com")
        self.assertEqual(parsed.path, "/connect/qrconnect")
        self.assertEqual(params["appid"], ["wx-app"])
        self.assertEqual(params["redirect_uri"], ["https://media-agent.createbeauty.top/auth/wechat/callback"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["scope"], ["snsapi_login"])
        self.assertEqual(params["state"], ["STATE123"])

    def test_auth_store_consumes_oauth_state_once(self):
        store = _auth_store()
        state = store.create_oauth_state(provider="wechat", next_path="/app")

        consumed = store.consume_oauth_state(state, provider="wechat")
        consumed_again = store.consume_oauth_state(state, provider="wechat")

        self.assertEqual(consumed, "/app")
        self.assertIsNone(consumed_again)

    def test_auth_store_creates_user_session_from_wechat_profile(self):
        store = _auth_store()

        user = store.upsert_external_user(
            provider="wechat",
            provider_user_id="openid-1",
            union_id="union-1",
            display_name="班森",
            profile={"headimgurl": "https://example.com/avatar.jpg"},
        )
        session_token = store.create_session(user.id)
        loaded = store.user_for_session(session_token)

        self.assertEqual(loaded["id"], user.id)
        self.assertEqual(loaded["display_name"], "班森")
        self.assertEqual(loaded["provider"], "wechat")

    def test_auth_store_creates_manual_wechat_user_and_account(self):
        store = _auth_store()

        user = store.create_manual_wechat_user(
            display_name="我的公众号",
            app_id="wx-manual-app",
            app_secret="manual-secret",
            access_token="manual-token",
        )
        session_token = store.create_session(user.id)
        account = store.manual_wechat_account_for_user(user.id)
        loaded = store.user_for_session(session_token)

        self.assertEqual(loaded["display_name"], "我的公众号")
        self.assertEqual(loaded["provider"], "manual_wechat")
        self.assertEqual(account["app_id"], "wx-manual-app")
        self.assertEqual(account["app_secret"], "manual-secret")
        self.assertEqual(account["access_token"], "manual-token")

    def test_auth_store_updates_manual_wechat_account_without_retyping_secret(self):
        store = _auth_store()
        user = store.create_manual_wechat_user(
            display_name="旧名称",
            app_id="wx-manual-app",
            app_secret="old-secret",
            access_token="old-token",
        )

        store.update_manual_wechat_account(
            user_id=user.id,
            display_name="新名称",
            app_id="wx-new-app",
            app_secret="",
            access_token="new-token",
        )
        account = store.manual_wechat_account_for_user(user.id)

        self.assertEqual(account["display_name"], "新名称")
        self.assertEqual(account["app_id"], "wx-new-app")
        self.assertEqual(account["app_secret"], "old-secret")
        self.assertEqual(account["access_token"], "new-token")


def _auth_store() -> AuthStore:
    tmpdir = tempfile.TemporaryDirectory()
    database_url = f"sqlite:///{Path(tmpdir.name) / 'auth.db'}"
    engine = build_engine(database_url)
    init_schema(engine)
    store = AuthStore(session_factory(engine))
    store._tmpdir = tmpdir
    return store


if __name__ == "__main__":
    unittest.main()
