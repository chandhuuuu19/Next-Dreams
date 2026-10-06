from __future__ import annotations

from datetime import datetime
from functools import lru_cache
import re
from typing import Any
import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_anon_key: str = ""
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "meta/llama-3.1-70b-instruct"
    frontend_origin: str = "http://localhost:3000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def settings() -> Settings:
    return Settings()


def user_client(access_token: str | None = None) -> Client:
    config = settings()
    if not config.supabase_url.startswith("https://") or not config.supabase_anon_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Supabase is not configured.")
    client = create_client(config.supabase_url, config.supabase_anon_key)
    if access_token:
        client.postgrest.auth(access_token)
    return client


class Credentials(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    password: str = Field(min_length=8, max_length=128)


class SignUp(Credentials):
    full_name: str = Field(min_length=1, max_length=120)
    role: str = "student"


class ProgressUpdate(BaseModel):
    skill_id: str
    status: str = Field(pattern="^(not_started|in_progress|completed)$")


class EmailRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class PasswordResetRequest(BaseModel):
    access_token: str = Field(min_length=20, max_length=4096)
    refresh_token: str = Field(min_length=20, max_length=4096)
    password: str = Field(min_length=8, max_length=128)


class GuidanceRequest(BaseModel):
    role: str = Field(pattern="^(student|parent|counsellor|content_editor|verifier|admin)$")
    prompt: str = Field(min_length=1, max_length=4000)


class CareerCatalogCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=180)
    title: str = Field(min_length=2, max_length=160)
    summary: str = Field(default="", max_length=2000)
    category: str = Field(min_length=2, max_length=120)
    minimum_education: str = Field(min_length=2, max_length=500)
    entry_stages: list[str] = Field(default_factory=list, max_length=5)
    eligible_streams: list[str] = Field(default_factory=list, max_length=20)
    education_pathways: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=40)
    typical_roles: list[str] = Field(default_factory=list, max_length=30)
    sources: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class CareerCatalogUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    summary: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, min_length=2, max_length=120)
    minimum_education: str | None = Field(default=None, min_length=2, max_length=500)
    entry_stages: list[str] | None = Field(default=None, max_length=5)
    eligible_streams: list[str] | None = Field(default=None, max_length=20)
    education_pathways: list[dict[str, Any]] | None = Field(default=None, max_length=100)
    skills: list[str] | None = Field(default=None, max_length=40)
    typical_roles: list[str] | None = Field(default=None, max_length=30)
    sources: list[dict[str, str]] | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class CareerCatalogVerification(BaseModel):
    verified_at: datetime
    sources: list[dict[str, str]] = Field(min_length=1, max_length=20)


app = FastAPI(title="Next Dreams API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings().frontend_origin or "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


def bearer(request: Request) -> str:
    value = request.headers.get("authorization", "")
    if not value.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in is required.")
    return value[7:].strip()


def current_user(token: str = Depends(bearer)) -> dict[str, Any]:
    try:
        result = user_client(token).auth.get_user(token)
        if not result.user:
            raise ValueError("No user")
        return {"id": result.user.id, "email": result.user.email}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is invalid or expired.") from exc


def require_staff(user: dict[str, Any] = Depends(current_user), token: str = Depends(bearer)) -> dict[str, Any]:
    try:
        rows = user_client(token).table("app_user_roles").select("role").eq("user_id", user["id"]).in_("role", ["content_editor", "verifier", "admin"]).execute().data or []
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Role service is unavailable.") from exc
    if not rows:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This action requires a staff role.")
    priority = {"admin": 3, "verifier": 2, "content_editor": 1}
    role = max((row["role"] for row in rows), key=lambda item: priority.get(item, 0))
    return {**user, "role": role}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "next-dreams-api"}


@app.get("/diagnostics")
def diagnostics() -> dict[str, Any]:
    """Report dependency connectivity without returning credentials or private data."""
    config = settings()
    supabase_state: dict[str, str] = {"status": "not_configured", "detail": "Set SUPABASE_URL and SUPABASE_ANON_KEY on the API."}
    if config.supabase_url.startswith("https://") and config.supabase_anon_key:
        try:
            user_client().table("education_levels").select("id").limit(1).execute()
            supabase_state = {"status": "connected", "detail": "Supabase responded to a read-only schema query."}
        except Exception:
            supabase_state = {"status": "unreachable", "detail": "Check Supabase URL/key, migration status, and network access."}
    nvidia_state = {"status": "configured", "detail": "NVIDIA NIM credentials are set."} if config.nvidia_api_key else {"status": "not_configured", "detail": "Set NVIDIA_API_KEY to enable role-specific model guidance."}
    return {"supabase": supabase_state, "nvidia": nvidia_state}


@app.get("/diagnostics/auth")
def auth_diagnostics() -> dict[str, Any]:
    """Describe auth configuration without contacting accounts or changing data."""
    config = settings()
    configured = bool(config.supabase_url.startswith("https://") and config.supabase_anon_key)
    return {
        "status": "configured" if configured else "not_configured",
        "provider": "supabase_auth",
        "safe_checks": ["health", "protected_route_requires_session", "privileged_self_signup_rejected", "request_validation"],
        "live_account_flows_tested": False,
        "detail": "Live account flows require a configured Supabase project and test account." if configured else "Set SUPABASE_URL and SUPABASE_ANON_KEY on the API to enable account flows.",
    }


@app.post("/guidance")
async def role_guidance(body: GuidanceRequest, user: dict[str, Any] = Depends(current_user), token: str = Depends(bearer)) -> dict[str, str]:
    config = settings()
    if not config.nvidia_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "NVIDIA guidance is not configured.")
    try:
        roles = user_client(token).table("app_user_roles").select("role").eq("user_id", user["id"]).execute().data or []
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Role service is unavailable.") from exc
    if body.role not in {item["role"] for item in roles}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Guidance is unavailable for this account role.")
    instructions = {
        "student": "Give age-appropriate educational and career exploration guidance. Explain options and encourage checking official admission requirements.",
        "parent": "Help a parent support a learner's choices without making decisions for them. Explain options, costs to investigate, and official sources to check.",
        "counsellor": "Support a counsellor with structured, neutral pathway comparisons and questions to ask. Flag uncertainty and verify official requirements.",
        "content_editor": "Help an editor improve clarity and completeness of career pathway content. Do not invent facts, citations, or admission requirements.",
        "verifier": "Help a verifier identify claims that need authoritative sources and inconsistencies. Never assert a claim is verified without evidence.",
        "admin": "Provide concise operational guidance. Do not infer permissions or disclose personal information.",
    }
    reasoning_style = " Use moderate reasoning: consider relevant tradeoffs before answering, be concise, and do not reveal private chain-of-thought."
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{config.nvidia_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {config.nvidia_api_key}", "Content-Type": "application/json"},
                json={"model": config.nvidia_model, "messages": [{"role": "system", "content": instructions[body.role] + reasoning_style}, {"role": "user", "content": body.prompt}], "temperature": 0.3, "max_tokens": 900},
            )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]
        return {"role": body.role, "answer": answer}
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "NVIDIA guidance service is unavailable.") from exc


@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def sign_up(body: SignUp) -> dict[str, Any]:
    # Self-service sign-up is student-only. Privileged roles are assigned out of band.
    if body.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choose a staff role through an administrator.")
    try:
        result = user_client().auth.sign_up({"email": body.email, "password": body.password, "options": {"data": {"full_name": body.full_name}}})
        if not result.user:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sign-up could not be completed.")
        return {"user_id": result.user.id, "confirmation_required": result.session is None}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sign-up could not be completed.") from exc


@app.post("/auth/signin")
def sign_in(body: Credentials) -> dict[str, Any]:
    try:
        result = user_client().auth.sign_in_with_password({"email": body.email, "password": body.password})
        if not result.session or not result.user:
            raise ValueError("No session")
        return {"access_token": result.session.access_token, "refresh_token": result.session.refresh_token, "expires_in": result.session.expires_in, "user": {"id": result.user.id, "email": result.user.email}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password was not accepted.") from exc


@app.post("/auth/refresh")
def refresh_session(body: RefreshRequest) -> dict[str, Any]:
    try:
        result = user_client().auth.refresh_session(body.refresh_token)
        if not result.session or not result.user:
            raise ValueError("No refreshed session")
        return {"access_token": result.session.access_token, "refresh_token": result.session.refresh_token, "expires_in": result.session.expires_in, "user": {"id": result.user.id, "email": result.user.email}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session could not be refreshed.") from exc


@app.post("/auth/signout", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(user: dict[str, Any] = Depends(current_user), token: str = Depends(bearer)) -> None:
    try:
        config = settings()
        response = httpx.post(
            f"{config.supabase_url.rstrip('/')}/auth/v1/logout",
            headers={"apikey": config.supabase_anon_key, "Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if response.status_code >= 400:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Session revocation failed; clear the local session and retry.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Session revocation is unavailable; clear the local session.") from exc


@app.post("/auth/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: PasswordResetRequest) -> None:
    try:
        client = user_client()
        client.auth.set_session(body.access_token, body.refresh_token)
        client.auth.update_user({"password": body.password})
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password reset could not be completed.") from exc


@app.post("/auth/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: EmailRequest) -> dict[str, str]:
    # Keep responses generic so callers cannot enumerate registered emails.
    email = body.email
    if email:
        try:
            user_client().auth.reset_password_email(email, {"redirect_to": f"{settings().frontend_origin}/?reset=1"})
        except Exception:
            pass
    return {"message": "If an account matches that address, reset instructions will be sent."}


@app.get("/me")
def me(user: dict[str, Any] = Depends(current_user), token: str = Depends(bearer)) -> dict[str, Any]:
    try:
        db = user_client(token)
        profile = db.table("student_profiles").select("display_name,education_stage,stream_id").eq("user_id", user["id"]).maybe_single().execute().data
        roles = db.table("app_user_roles").select("role").eq("user_id", user["id"]).execute().data or []
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Profile service is unavailable.") from exc
    return {**user, "profile": profile, "roles": [row["role"] for row in roles]}


@app.get("/careers")
def careers(q: str | None = None) -> list[dict[str, Any]]:
    try:
        query = user_client().table("career_paths").select("id,name,summary,source_status").eq("published", True)
        if q:
            query = query.ilike("name", f"%{q}%")
        return query.order("name").limit(100).execute().data or []
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Career data is unavailable.") from exc


@app.get("/career-catalog")
def search_career_catalog(
    q: str | None = None,
    stream: str | None = None,
    category: str | None = None,
    education_level: str | None = None,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=24, ge=1, le=60),
) -> dict[str, Any]:
    """Search the expandable catalog with indexed filters; includes draft labels for cautious exploration."""
    allowed_streams = {"MPC", "BiPC", "MEC", "CEC", "Humanities", "Arts", "Vocational", "Any"}
    allowed_stages = {"After Class 10", "After Class 12 / Intermediate", "After Graduation"}
    if stream and stream not in allowed_streams:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown stream filter.")
    if education_level and education_level not in allowed_stages:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown education-level filter.")
    if q and (len(q) > 100 or not re.fullmatch(r"[\w\s&.+/-]+", q, flags=re.UNICODE)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Search may contain letters, numbers and basic separators only.")
    if category and (len(category) > 120 or not re.fullmatch(r"[\w\s&/-]+", category, flags=re.UNICODE)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid category filter.")
    try:
        query = user_client().table("career_catalog").select(
            "slug,title,summary,category,minimum_education,entry_stages,eligible_streams,education_pathways,skills,typical_roles,sources,source_status,verified_at",
            count="exact",
        ).eq("is_active", True)
        if stream:
            query = query.overlaps("eligible_streams", [stream, "Any"])
        if education_level:
            query = query.overlaps("entry_stages", [education_level])
        if category:
            category_groups = {
                "Technology": ["computer science", "computer science and business", "engineering", "engineering and technology", "science and sustainability", "green and energy careers"],
                "Healthcare": ["healthcare", "allied health", "life sciences", "healthcare and life sciences", "social sciences and health"],
                "Commerce": ["commerce and finance", "commerce and social sciences", "business and management", "business and communication", "business and self-employment"],
                "Law and public service": ["law and public service", "government and public service", "government and defence"],
                "Creative industries": ["creative industries", "creative industries and technology", "media and communication"],
                "Vocational education": ["vocational education", "skilled trades"],
            }
            if category in category_groups:
                query = query.in_("category", category_groups[category])
            else:
                query = query.ilike("category", f"%{category}%")
        if q:
            search_terms = " & ".join(re.findall(r"[\w]+", q, flags=re.UNICODE))
            if search_terms:
                query = query.text_search("search_document", search_terms, options={"config": "simple"})
        result = query.order("title").range((page - 1) * limit, page * limit - 1).execute()
        return {"items": result.data or [], "page": page, "limit": limit, "total": result.count or 0}
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Career catalog is unavailable; apply its Supabase migration and seed first.") from exc


@app.post("/admin/career-catalog", status_code=status.HTTP_201_CREATED)
def create_catalog_career(body: CareerCatalogCreate, staff: dict[str, Any] = Depends(require_staff), token: str = Depends(bearer)) -> dict[str, Any]:
    if staff["role"] not in {"content_editor", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A content editor or admin role is required.")
    try:
        payload = body.model_dump()
        payload["source_status"] = "draft"
        payload["is_active"] = True
        response = user_client(token).table("career_catalog").insert(payload).execute()
        return response.data[0]
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Career could not be added; check whether its slug already exists.") from exc


@app.patch("/admin/career-catalog/{slug}")
def update_catalog_career(slug: str, body: CareerCatalogUpdate, staff: dict[str, Any] = Depends(require_staff), token: str = Depends(bearer)) -> dict[str, Any]:
    if staff["role"] not in {"content_editor", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A content editor or admin role is required.")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide at least one field to update.")
    if "sources" in changes:
        changes["source_status"] = "stale"
        changes["verified_at"] = None
    try:
        response = user_client(token).table("career_catalog").update(changes).eq("slug", slug).execute()
        if not response.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Career was not found.")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Career could not be updated.") from exc


@app.post("/admin/career-catalog/{slug}/verify")
def verify_catalog_career(slug: str, body: CareerCatalogVerification, staff: dict[str, Any] = Depends(require_staff), token: str = Depends(bearer)) -> dict[str, Any]:
    if staff["role"] not in {"verifier", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A verifier or admin role is required.")
    if any(not source.get("name") or not source.get("url", "").startswith("https://") for source in body.sources):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Each verification source needs a name and HTTPS URL.")
    try:
        result = user_client(token).rpc("verify_career_catalog", {
            "target_slug": slug,
            "source_evidence": body.sources,
            "verified_on": body.verified_at.isoformat(),
        }).execute().data
        if not result:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Career was not found.")
        return {"status": "verified", "career": result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Career verification could not be saved.") from exc


@app.get("/careers/{career_id}/roadmap")
def career_roadmap(career_id: str) -> dict[str, Any]:
    try:
        db = user_client()
        career = db.table("career_paths").select("id,name,summary").eq("id", career_id).eq("published", True).single().execute().data
        stages = db.table("roadmap_stages").select("id,title,sequence,description,roadmap_skills(skill_id,skills(id,name,level))").eq("career_path_id", career_id).order("sequence").execute().data
        return {"career": career, "stages": stages or []}
    except HTTPException:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if "0 rows" in message or "not found" in message:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Published career pathway was not found.") from exc
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Career pathway data is unavailable.") from exc


@app.patch("/me/skills")
def update_skill_progress(body: ProgressUpdate, user: dict[str, Any] = Depends(current_user), token: str = Depends(bearer)) -> dict[str, Any]:
    try:
        row = user_client(token).table("skill_progress").upsert({"user_id": user["id"], "skill_id": body.skill_id, "status": body.status}, on_conflict="user_id,skill_id").execute().data
        return {"progress": row[0] if row else {"skill_id": body.skill_id, "status": body.status}}
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Skill progress could not be updated.") from exc


@app.patch("/admin/careers/{career_id}/publish")
def publish_career(career_id: str, staff: dict[str, Any] = Depends(require_staff), token: str = Depends(bearer)) -> dict[str, str]:
    try:
        if staff["role"] not in {"verifier", "admin"}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a verifier or admin can publish a pathway.")
        result = user_client(token).rpc("publish_career_path", {"target": career_id}).execute().data
        if not result:
            raise HTTPException(status.HTTP_409_CONFLICT, "Record a verified source before publishing.")
        return {"status": "published"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Career pathway could not be published.") from exc

