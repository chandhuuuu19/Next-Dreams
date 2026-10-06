import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from fastapi import HTTPException

from app.main import app, auth_diagnostics, bearer, current_user, require_staff
from app import main as api


class ApiSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        app.dependency_overrides[current_user] = lambda: {"id": "00000000-0000-0000-0000-000000000001"}
        app.dependency_overrides[bearer] = lambda: "test-access-token"
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_health_is_available_without_database_credentials(self):
        response = await self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "next-dreams-api")

    async def test_diagnostics_reports_unconfigured_services_without_secrets(self):
        with patch("app.main.settings") as configured:
            configured.return_value.supabase_url = ""
            configured.return_value.supabase_anon_key = ""
            configured.return_value.nvidia_api_key = ""
            response = await self.client.get("/diagnostics")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["supabase"]["status"], "not_configured")
        self.assertEqual(payload["nvidia"]["status"], "not_configured")
        self.assertNotIn("test-secret-value", str(payload))

    async def test_auth_diagnostics_discloses_only_safe_configuration_state(self):
        with patch("app.main.settings") as configured:
            configured.return_value.supabase_url = ""
            configured.return_value.supabase_anon_key = ""
            payload = auth_diagnostics()
        self.assertEqual(payload["status"], "not_configured")
        self.assertFalse(payload["live_account_flows_tested"])
        self.assertIn("protected_route_requires_session", payload["safe_checks"])
        self.assertNotIn("test-secret-value", str(payload))

    async def test_privileged_self_signup_is_rejected(self):
        response = await self.client.post("/auth/signup", json={
            "email": "admin@example.test", "password": "not-a-real-password",
            "full_name": "Demo Admin", "role": "admin",
        })
        self.assertEqual(response.status_code, 403)

    async def test_auth_service_fails_closed_without_supabase_configuration(self):
        with patch("app.main.user_client", side_effect=HTTPException(503, "Supabase is not configured.")):
            response = await self.client.post("/auth/signin", json={
                "email": "student@example.test", "password": "not-a-real-password",
            })
        self.assertEqual(response.status_code, 503)

    async def test_protected_route_preserves_supabase_configuration_error(self):
        app.dependency_overrides.clear()
        app.dependency_overrides[bearer] = lambda: "test-access-token"
        with patch("app.main.user_client", side_effect=HTTPException(503, "Supabase is not configured.")):
            response = await self.client.get("/me", headers={"Authorization": "Bearer test-access-token"})
        self.assertEqual(response.status_code, 503)

    async def test_protected_skill_progress_requires_session(self):
        app.dependency_overrides.clear()
        response = await self.client.patch("/me/skills", json={
            "skill_id": "00000000-0000-0000-0000-000000000001", "status": "completed",
        })
        self.assertEqual(response.status_code, 401)

    async def test_career_catalog_filters_validate_before_querying_the_database(self):
        invalid_stream = await self.client.get("/career-catalog?stream=NOT-A-STREAM")
        invalid_search = await self.client.get("/career-catalog?q=%3Cscript%3E")
        oversized_page = await self.client.get("/career-catalog?limit=100")
        self.assertEqual(invalid_stream.status_code, 422)
        self.assertEqual(invalid_search.status_code, 422)
        self.assertEqual(oversized_page.status_code, 422)

    async def test_career_catalog_search_uses_database_filters_and_pagination(self):
        calls = []

        class Query:
            def select(self, *_args, **_kwargs): return self
            def eq(self, *args): calls.append(("eq", args)); return self
            def overlaps(self, *args): calls.append(("overlaps", args)); return self
            def in_(self, *args): calls.append(("in", args)); return self
            def text_search(self, *args, **kwargs): calls.append(("text_search", args, kwargs)); return self
            def order(self, *args): calls.append(("order", args)); return self
            def range(self, *args): calls.append(("range", args)); return self
            def execute(self): return type("Result", (), {"data": [{"slug": "data-science"}], "count": 52})()

        class Database:
            def table(self, _name): return Query()

        with patch("app.main.user_client", return_value=Database()):
            response = await self.client.get("/career-catalog?q=data+science&stream=MPC&education_level=After+Class+10&page=2&limit=10")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"items": [{"slug": "data-science"}], "page": 2, "limit": 10, "total": 52})
        self.assertIn(("overlaps", ("eligible_streams", ["MPC", "Any"])), calls)
        self.assertIn(("overlaps", ("entry_stages", ["After Class 10"])), calls)
        self.assertIn(("range", (10, 19)), calls)
        self.assertTrue(any(call[0] == "text_search" for call in calls))

    async def test_progress_status_validation(self):
        response = await self.client.patch("/me/skills", headers={"Authorization": "Bearer invalid"}, json={
            "skill_id": "00000000-0000-0000-0000-000000000001", "status": "passed",
        })
        self.assertEqual(response.status_code, 422)

    async def test_staff_role_resolution_prefers_verifier_over_editor(self):
        class Query:
            def select(self, *_args): return self
            def eq(self, *_args): return self
            def in_(self, *_args): return self
            def execute(self):
                return type("Result", (), {"data": [{"role": "content_editor"}, {"role": "verifier"}]})()

        class Database:
            def table(self, _name): return Query()

        with patch("app.main.user_client", return_value=Database()):
            staff = require_staff({"id": "user-1"}, "token")
        self.assertEqual(staff["role"], "verifier")

    async def test_nvidia_guidance_uses_authorized_role_specific_instructions(self):
        roles = ["student", "parent", "counsellor", "content_editor", "verifier", "admin"]
        prompts = []

        class Query:
            def select(self, *_args): return self
            def eq(self, *_args): return self
            def execute(self):
                return type("Result", (), {"data": [{"role": role} for role in roles]})()

        class Database:
            def table(self, _name): return Query()

        class FakeNvidiaClient:
            def __init__(self, **_kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def post(self, _url, *, headers, json):
                self.assert_secret_not_returned = "Bearer test-nvidia-key" in headers["Authorization"]
                prompts.append(json["messages"][0]["content"])
                return type("Response", (), {
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {"choices": [{"message": {"content": "Role-aware guidance"}}]},
                })()

        config = type("Config", (), {
            "nvidia_api_key": "test-nvidia-key",
            "nvidia_base_url": "https://nvidia.example.test/v1",
            "nvidia_model": "test-model",
        })()
        with patch("app.main.settings", return_value=config), \
             patch("app.main.user_client", return_value=Database()), \
             patch("app.main.httpx.AsyncClient", FakeNvidiaClient):
            for role in roles:
                response = await self.client.post("/guidance", json={"role": role, "prompt": "Suggest a next step."})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["role"], role)

        self.assertEqual(len(set(prompts)), len(roles))
        self.assertTrue(all("moderate reasoning" in prompt for prompt in prompts))
        for phrase in ["age-appropriate", "parent", "counsellor", "editor", "verifier", "operational"]:
            self.assertTrue(any(phrase in prompt.lower() for prompt in prompts), phrase)


if __name__ == "__main__":
    unittest.main()
