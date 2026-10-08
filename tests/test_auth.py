import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib import parse

from content_agent.auth import (
    AuthStore,
    ServerOwnerConfig,
    WeChatComponentConfig,
    WeChatComponentProvider,
    WeChatLoginConfig,
    WeChatOAuthProvider,
    parse_wechat_component_event,
)
from content_agent.database import build_engine, init_schema, session_factory


class AuthTests(unittest.TestCase):
    def test_server_owner_config_authenticates_without_exposing_wechat_credentials(self):
        values = {
            "OWNER_LOGIN_PASSWORD": "a-long-owner-password",
            "OWNER_DISPLAY_NAME": "班森",
            "WECHAT_APP_ID": "wx-server-app",
            "WECHAT_APP_SECRET": "server-secret",
            "WECHAT_ACCESS_TOKEN": "server-token",
        }

        with patch.dict("os.environ", values, clear=True):
            config = ServerOwnerConfig.from_env()

        self.assertTrue(config.is_configured())
        self.assertTrue(config.authenticate("a-long-owner-password"))
        self.assertFalse(config.authenticate("wrong-password"))
        self.assertEqual(config.display_name, "班森")
        self.assertEqual(config.wechat_app_id, "wx-server-app")

    def test_server_owner_config_requires_login_password_and_wechat_credentials(self):
        with patch.dict("os.environ", {"WECHAT_APP_ID": "wx-server-app"}, clear=True), patch("content_agent.auth._read_env_value", return_value=""):
            config = ServerOwnerConfig.from_env()

        self.assertFalse(config.is_configured())
        self.assertFalse(config.authenticate(""))

    def test_auth_store_creates_owner_session_from_server_wechat_config(self):
        store = _auth_store()
        config = ServerOwnerConfig(
            login_password="owner-password-1234",
            display_name="班森",
            wechat_app_id="wx-server-app",
            wechat_app_secret="server-secret",
            wechat_access_token="server-token",
        )

        session_token = store.create_server_owner_session(config, "owner-password-1234")
        user = store.user_for_session(session_token)
        account = store.manual_wechat_account_for_user(user["id"])

        self.assertEqual(user["display_name"], "班森")
        self.assertEqual(account["app_id"], "wx-server-app")
        self.assertEqual(account["app_secret"], "server-secret")

    def test_auth_store_rejects_wrong_server_owner_password(self):
        store = _auth_store()
        config = ServerOwnerConfig(
            login_password="owner-password-1234",
            wechat_app_id="wx-server-app",
            wechat_app_secret="server-secret",
        )

        with self.assertRaisesRegex(ValueError, "管理员密码不正确"):
            store.create_server_owner_session(config, "wrong-password")

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

    def test_wechat_component_provider_builds_official_account_auth_url(self):
        provider = WeChatComponentProvider(
            WeChatComponentConfig(
                app_id="wx-component",
                app_secret="component-secret",
                token="verify-token",
                aes_key="abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
                auth_redirect_uri="https://media-agent.createbeauty.top/auth/wechat-official/callback",
            )
        )

        url = provider.authorization_url(pre_auth_code="PRE_AUTH_CODE")
        parsed = parse.urlparse(url)
        params = parse.parse_qs(parsed.query)

        self.assertEqual(parsed.netloc, "mp.weixin.qq.com")
        self.assertEqual(parsed.path, "/cgi-bin/componentloginpage")
        self.assertEqual(params["component_appid"], ["wx-component"])
        self.assertEqual(params["pre_auth_code"], ["PRE_AUTH_CODE"])
        self.assertEqual(
            params["redirect_uri"],
            ["https://media-agent.createbeauty.top/auth/wechat-official/callback"],
        )
        self.assertEqual(params["auth_type"], ["3"])

    def test_auth_store_saves_component_authorized_wechat_account(self):
        store = _auth_store()
        user = store.upsert_external_user(provider="wechat", provider_user_id="openid-1", display_name="用户")

        store.upsert_component_wechat_account(
            user_id=user.id,
            authorizer_appid="wx-authorizer",
            display_name="授权公众号",
            authorizer_refresh_token="refresh-token",
            authorizer_access_token="access-token",
            expires_in=7200,
            profile={"nick_name": "授权公众号"},
        )

        account = store.component_wechat_account_for_user(user.id)
        self.assertEqual(account["auth_type"], "component")
        self.assertEqual(account["authorizer_appid"], "wx-authorizer")
        self.assertEqual(account["display_name"], "授权公众号")
        self.assertEqual(account["authorizer_refresh_token"], "refresh-token")
        self.assertEqual(account["authorizer_access_token"], "access-token")
        self.assertEqual(account["profile"]["nick_name"], "授权公众号")

    def test_auth_store_saves_component_verify_ticket_from_event(self):
        store = _auth_store()

        store.save_wechat_component_verify_ticket("ticket-123")

        self.assertEqual(store.wechat_component_verify_ticket(), "ticket-123")

    def test_parse_wechat_component_plain_ticket_event(self):
        raw_xml = """
        <xml>
          <InfoType><![CDATA[component_verify_ticket]]></InfoType>
          <ComponentVerifyTicket><![CDATA[ticket-123]]></ComponentVerifyTicket>
        </xml>
        """

        event = parse_wechat_component_event(
            raw_xml,
            config=WeChatComponentConfig(app_id="wx-component", token="token"),
            query_params={},
        )

        self.assertEqual(event["InfoType"], "component_verify_ticket")
        self.assertEqual(event["ComponentVerifyTicket"], "ticket-123")


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
