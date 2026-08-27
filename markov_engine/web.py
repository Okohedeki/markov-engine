"""Focused server-rendered customer and reviewer workflow for Markov V1."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from markov_engine.billing import public_catalog
from markov_engine.config import Settings
from markov_engine.exports import export_artifact
from markov_engine.jobs import run_job, submit_job
from markov_engine.research import convert_case_artifact
from markov_engine.reviews import finalize_review, record_review_decision
from markov_engine.revisions import deepen_claim, revise_script_section

_CSS = """
:root{color-scheme:light;--ink:#17201f;--muted:#62706e;--paper:#f7f5ee;
--card:#fff;--accent:#075e54;--line:#dce2df}*{box-sizing:border-box}body{margin:0;
font:16px/1.55 Inter,ui-sans-serif,system-ui;color:var(--ink);background:var(--paper)}
main{max-width:1080px;margin:auto;padding:32px 20px 72px}header{display:flex;align-items:center;
justify-content:space-between;margin-bottom:36px}.brand{font-size:22px;font-weight:800;letter-spacing:-.03em}
a{color:var(--accent)}.hero{max-width:720px;margin:56px 0}.hero h1{font-size:clamp(40px,7vw,72px);
line-height:.95;letter-spacing:-.06em;margin:0 0 24px}.muted{color:var(--muted)}.grid{display:grid;
grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}.card{background:var(--card);
border:1px solid var(--line);border-radius:14px;padding:22px;box-shadow:0 8px 30px #193b3220}
label{display:block;font-weight:700;margin:16px 0 6px}input,select,textarea{width:100%;font:inherit;
padding:11px 12px;border:1px solid #aebbb7;border-radius:8px;background:#fff}textarea{min-height:130px}
button,.button{display:inline-block;border:0;border-radius:999px;padding:11px 18px;background:var(--accent);
color:#fff;font-weight:800;text-decoration:none;cursor:pointer;margin:8px 6px 0 0}.secondary{background:#e6eeeb;
color:var(--ink)}.danger{background:#99392f}.pill{display:inline-block;padding:4px 9px;border-radius:999px;
background:#e6eeeb;font-size:13px;font-weight:700}.timeline{border-left:2px solid var(--line);padding-left:20px}
.timeline p{position:relative}.timeline p:before{content:'';position:absolute;left:-26px;top:8px;width:10px;
height:10px;border-radius:50%;background:var(--accent)}pre.artifact{white-space:pre-wrap;font:15px/1.65 ui-monospace,
SFMono-Regular,Consolas;background:#101817;color:#ecf6f2;border-radius:12px;padding:22px;overflow:auto}
details{border-top:1px solid var(--line);padding:12px 0}.error{background:#ffe9e6;color:#7c211a;
padding:12px;border-radius:8px}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.row>*{flex:1}
small{color:var(--muted)}@media(max-width:640px){main{padding-top:20px}.hero{margin:32px 0}}
"""


def _page(title: str, content: str, *, refresh: int | None = None) -> HTMLResponse:
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return HTMLResponse(
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{meta}<title>{html.escape(title)} · Markov</title><style>{_CSS}</style></head>"
        '<body><main><header><a class="brand" href="/app">MARKOV</a>'
        '<span class="muted">Brief · Research · Script</span></header>'
        f"{content}</main></body></html>"
    )


async def _form(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode("utf-8", errors="replace")
    return {key: values[-1] for key, values in parse_qs(raw).items()}


def _signed(identity: str, secret: str) -> str:
    encoded = base64.urlsafe_b64encode(identity.encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _unsigned(value: str | None, secret: str) -> str | None:
    if not value or "." not in value:
        return None
    encoded, signature = value.rsplit(".", 1)
    expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None


def _safe_link(url: str | None, label: str) -> str:
    parsed = urlparse(url or "")
    safe_label = html.escape(label)
    if parsed.scheme not in {"http", "https"}:
        return safe_label
    return f'<a href="{html.escape(url or "", quote=True)}" target="_blank" rel="noopener">{safe_label}</a>'


def create_web_router(*, settings: Settings) -> APIRouter:
    router = APIRouter()

    def owner(request: Request) -> str:
        identity = _unsigned(request.cookies.get("markov_session"), settings.web_session_secret)
        if not identity or identity not in set(settings.api_keys.values()):
            raise HTTPException(status_code=401, detail="Sign in at /app/login")
        return identity

    def reviewer(request: Request) -> str:
        identity = _unsigned(request.cookies.get("markov_reviewer"), settings.web_session_secret)
        if not identity or identity not in set(settings.internal_api_keys.values()):
            raise HTTPException(status_code=401, detail="Sign in at /app/reviewer/login")
        return identity

    @router.get("/app/login")
    async def login_page():
        return _page(
            "Sign in",
            '<section class="hero"><h1>Finished research, not another workspace.</h1>'
            '<p class="muted">Use your Markov API key to open your private projects.</p>'
            '<form method="post"><label>API key</label><input name="api_key" type="password" required>'
            '<button>Sign in</button></form></section>',
        )

    @router.post("/app/login")
    async def login(request: Request):
        values = await _form(request)
        owner_id = settings.api_keys.get(values.get("api_key", ""))
        if not owner_id:
            return _page("Sign in", '<p class="error">That API key is not valid.</p>')
        response = RedirectResponse("/app", status_code=303)
        response.set_cookie(
            "markov_session",
            _signed(owner_id, settings.web_session_secret),
            httponly=True,
            samesite="strict",
            max_age=60 * 60 * 24 * 30,
        )
        return response

    @router.get("/app")
    async def intake(request: Request):
        try:
            owner_id = owner(request)
        except HTTPException:
            return RedirectResponse("/app/login", status_code=303)
        store = request.app.state.store
        account = await store.get_credit_account(owner_id)
        jobs = await store.list_jobs(owner_id=owner_id, limit=12)
        history = "".join(
            f'<li><a href="/app/jobs/{html.escape(job.id)}">{html.escape(job.mode.title())}</a> '
            f'<span class="pill">{html.escape(job.status.replace("_", " "))}</span></li>'
            for job in jobs
        ) or "<li>No projects yet.</li>"
        products = "".join(
            f"<li>{html.escape(item['variant'])}: {item['credit_cost']:g} credits</li>"
            for item in public_catalog(settings)
        )
        return _page(
            "Create",
            '<section class="hero"><p class="pill">One shared research case</p>'
            '<h1>What should Markov work with?</h1>'
            '<p class="muted">Paste a URL, topic, or question. Markov preserves source locations, '
            "tests the important claims, and delivers a finished artifact.</p></section>"
            '<section class="grid"><form class="card" method="post" action="/app/jobs">'
            '<label>Topic, question, or public URL</label><textarea name="value" required></textarea>'
            '<div class="row"><div><label>Output</label><select name="mode">'
            '<option value="brief">Brief it</option><option value="research">Research it</option>'
            '<option value="script">Script it</option></select></div><div><label>Quality</label>'
            '<select name="review_level"><option value="instant">Instant</option>'
            '<option value="verified">Verified</option></select></div></div>'
            '<label>Focus or research question</label><input name="focus">'
            '<div class="row"><div><label>Target minutes (scripts)</label><input name="target_minutes" '
            'type="number" min="1" max="120" value="8"></div><div><label>Audience</label>'
            '<input name="audience" value="general"></div></div><label>Tone</label>'
            '<input name="tone" value="clear documentary"><button>Create</button></form>'
            f'<aside class="card"><h2>{account.balance:g} credits</h2><details><summary>Product costs</summary>'
            f"<ul>{products}</ul></details><h3>Recent projects</h3><ul>{history}</ul></aside></section>",
        )

    @router.post("/app/jobs")
    async def create_job_page(
        request: Request, background_tasks: BackgroundTasks
    ):
        owner_id = owner(request)
        values = await _form(request)
        value = values.get("value", "").strip()
        input_type = "url" if urlparse(value).scheme in {"http", "https"} else "text"
        constraints = {
            key: values[key]
            for key in ("focus", "audience", "tone")
            if values.get(key)
        }
        if values.get("target_minutes"):
            constraints["target_minutes"] = float(values["target_minutes"])
        try:
            job, created = await submit_job(
                request.app.state.store,
                owner_id=owner_id,
                mode=values.get("mode", "brief"),
                review_level=values.get("review_level", "instant"),
                inputs=[{"type": input_type, "value": value}],
                constraints=constraints,
                settings=settings,
            )
        except ValueError as exc:
            return _page("Could not create", f'<p class="error">{html.escape(str(exc))}</p>')
        if created:
            background_tasks.add_task(
                run_job,
                request.app.state.store,
                job_id=job.id,
                settings=settings,
                process_case=request.app.state.process_case,
            )
        return RedirectResponse(f"/app/jobs/{job.id}", status_code=303)

    @router.get("/app/jobs/{job_id}")
    async def job_page(job_id: str, request: Request):
        owner_id = owner(request)
        store = request.app.state.store
        job = await store.get_job(job_id, owner_id=owner_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        events = await store.list_job_events(job.id)
        timeline = "".join(
            f"<p><strong>{html.escape(event.stage.replace('_', ' ').title())}</strong> "
            f"<small>{html.escape(str(event.detail))}</small></p>"
            for event in events
        )
        artifacts = await store.list_case_artifacts(job.research_case_id)
        links = "".join(
            f'<a class="button" href="/app/artifacts/{item.id}">Open {html.escape(item.artifact_type.replace("_", " ").title())}</a>'
            for item in artifacts
        )
        error = f'<p class="error">{html.escape(job.error)}</p>' if job.error else ""
        refresh = None if job.status in {"completed", "failed", "awaiting_review"} else 4
        return _page(
            "Processing",
            f'<p class="pill">{html.escape(job.status.replace("_", " ").title())}</p>'
            f"<h1>{html.escape(job.mode.title())} job</h1>{error}"
            f'<section class="card timeline">{timeline}</section><p>{links}</p>',
            refresh=refresh,
        )

    @router.get("/app/artifacts/{artifact_id}")
    async def artifact_page(artifact_id: int, request: Request):
        owner_id = owner(request)
        store = request.app.state.store
        artifact = await store.get_artifact(artifact_id, owner_id=owner_id)
        if artifact is None or artifact.research_case_id is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        case = await store.get_research_case(artifact.research_case_id, owner_id=owner_id)
        claims = await store.list_claims(case.id)
        gaps = await store.list_research_gaps(case.id)
        sources = await store.list_research_case_sources(case.id)
        await store.record_usage_event(
            owner_id=owner_id,
            event_type="artifact_viewed",
            research_case_id=case.id,
            artifact_id=artifact.id,
        )
        source_html = "".join(
            f"<li>{_safe_link(source.get('url'), source.get('title') or 'Source')} "
            f"<span class=\"pill\">{html.escape(source.get('source_quality') or 'unclassified')}</span> "
            f"<small>{html.escape(source.get('source_quality_rationale') or '')}</small></li>"
            for source in sources
        )
        claim_html = []
        for claim in claims:
            evidence = await store.list_claim_evidence(claim.id)
            evidence_html = "".join(
                f"<li><strong>{html.escape(link.stance)}</strong>: "
                f"{html.escape(link.evidence.passage_text if link.evidence else '')} "
                f"<small>{html.escape(link.rationale)}</small></li>"
                for link in evidence
            ) or "<li>No independent passage obtained.</li>"
            claim_html.append(
                f"<details><summary>C{claim.id}: {html.escape(claim.claim_text)} "
                f"<span class=\"pill\">{html.escape(claim.verification_status)}</span></summary>"
                f"<ul>{evidence_html}</ul><form method=\"post\" action=\"/app/claims/{claim.id}/deepen\">"
                f'<input type="hidden" name="return_artifact" value="{artifact.id}"><button>Deepen this</button></form></details>'
            )
        gap_html = "".join(
            f"<li>{html.escape(gap.question)} <span class=\"pill\">{html.escape(gap.status)}</span></li>"
            for gap in gaps
        ) or "<li>No explicit gaps.</li>"
        conversion = "".join(
            f'<form method="post" action="/app/cases/{case.id}/convert" style="display:inline">'
            f'<input type="hidden" name="mode" value="{mode}"><input type="hidden" name="review_level" value="instant">'
            f'<button class="secondary">Convert to {label}</button></form>'
            for mode, label in (("brief", "Brief"), ("research", "Research"), ("script", "Script"))
        )
        revision = ""
        if artifact.artifact_type == "script":
            options = "".join(
                f'<option value="{html.escape(str(section.get("id")))}">{html.escape(str(section.get("title")))}</option>'
                for section in (artifact.structured_content or {}).get("sections", [])
            )
            revision = (
                f'<section class="card"><h2>Revise one section</h2><form method="post" '
                f'action="/app/artifacts/{artifact.id}/revisions"><label>Section</label><select name="section_id">'
                f"{options}</select><label>Replacement</label><textarea name=\"replacement\" required></textarea>"
                "<small>Existing claim and evidence markers may be reused; new ones are rejected.</small><br><button>Save revision</button></form></section>"
            )
        return _page(
            artifact.title,
            f'<div class="row"><div><p class="pill">{html.escape(artifact.review_level.title())} · '
            f'{html.escape(artifact.status.replace("_", " ").title())}</p><h1>{html.escape(artifact.title)}</h1></div>'
            f'<div><a class="button" href="/app/artifacts/{artifact.id}/export?format=markdown">Export Markdown</a>'
            f'<a class="button secondary" href="/app/artifacts/{artifact.id}/export?format=html">Export HTML</a></div></div>'
            f'<pre class="artifact">{html.escape(artifact.content)}</pre><section class="card"><h2>Convert</h2>{conversion}</section>'
            f'<section class="grid"><div class="card"><h2>Claim ledger</h2>{"".join(claim_html)}</div>'
            f'<div class="card"><h2>Sources</h2><ul>{source_html}</ul><h2>Research gaps</h2><ul>{gap_html}</ul></div></section>{revision}',
        )

    @router.get("/app/artifacts/{artifact_id}/export")
    async def artifact_export(
        artifact_id: int, request: Request, format: str = "markdown"
    ):
        owner_id = owner(request)
        try:
            content, media_type, filename = await export_artifact(
                request.app.state.store,
                artifact_id=artifact_id,
                owner_id=owner_id,
                export_format=format,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/app/cases/{case_id}/convert")
    async def convert_page(case_id: int, request: Request):
        owner_id = owner(request)
        values = await _form(request)
        try:
            artifact, _ = await convert_case_artifact(
                request.app.state.store,
                case_id=case_id,
                owner_id=owner_id,
                mode=values.get("mode", "brief"),
                review_level=values.get("review_level", "instant"),
                settings=settings,
            )
        except ValueError as exc:
            return _page("Could not convert", f'<p class="error">{html.escape(str(exc))}</p>')
        return RedirectResponse(f"/app/artifacts/{artifact.id}", status_code=303)

    @router.post("/app/claims/{claim_id}/deepen")
    async def deepen_page(claim_id: int, request: Request):
        owner_id = owner(request)
        values = await _form(request)
        return_artifact = int(values.get("return_artifact") or 0)
        try:
            await deepen_claim(
                request.app.state.store, claim_id=claim_id, owner_id=owner_id
            )
        except ValueError as exc:
            return _page("Could not deepen", f'<p class="error">{html.escape(str(exc))}</p>')
        return RedirectResponse(f"/app/artifacts/{return_artifact}", status_code=303)

    @router.post("/app/artifacts/{artifact_id}/revisions")
    async def revise_page(artifact_id: int, request: Request):
        owner_id = owner(request)
        values = await _form(request)
        try:
            await revise_script_section(
                request.app.state.store,
                artifact_id=artifact_id,
                section_id=values.get("section_id", ""),
                replacement=values.get("replacement", ""),
                owner_id=owner_id,
            )
        except ValueError as exc:
            return _page("Could not revise", f'<p class="error">{html.escape(str(exc))}</p>')
        return RedirectResponse(f"/app/artifacts/{artifact_id}", status_code=303)

    @router.get("/app/reviewer/login")
    async def reviewer_login_page():
        return _page(
            "Reviewer sign in",
            '<h1>Reviewer queue</h1><form method="post"><label>Internal reviewer key</label>'
            '<input name="api_key" type="password" required><button>Sign in</button></form>',
        )

    @router.post("/app/reviewer/login")
    async def reviewer_login(request: Request):
        values = await _form(request)
        reviewer_id = settings.internal_api_keys.get(values.get("api_key", ""))
        if not reviewer_id:
            return _page("Reviewer sign in", '<p class="error">Invalid reviewer key.</p>')
        response = RedirectResponse("/app/reviews", status_code=303)
        response.set_cookie(
            "markov_reviewer",
            _signed(reviewer_id, settings.web_session_secret),
            httponly=True,
            samesite="strict",
            max_age=60 * 60 * 12,
        )
        return response

    @router.get("/app/reviews")
    async def review_queue(request: Request):
        try:
            reviewer(request)
        except HTTPException:
            return RedirectResponse("/app/reviewer/login", status_code=303)
        reviews = await request.app.state.store.list_review_jobs()
        items = "".join(
            f'<li><a href="/app/reviews/{item.id}">Review {item.id}</a> — artifact {item.artifact_id} '
            f'<span class="pill">{html.escape(item.status)}</span></li>'
            for item in reviews
        ) or "<li>Queue is empty.</li>"
        return _page("Reviewer queue", f"<h1>Reviewer queue</h1><ul>{items}</ul>")

    @router.get("/app/reviews/{review_id}")
    async def review_page(review_id: int, request: Request):
        reviewer(request)
        store = request.app.state.store
        review_job = await store.get_review_job(review_id)
        if review_job is None:
            raise HTTPException(status_code=404, detail="Review not found")
        artifact = await store.get_artifact(review_job.artifact_id)
        if artifact is None or artifact.research_case_id is None:
            raise HTTPException(status_code=404, detail="Reviewed artifact not found")
        case = await store.get_research_case(artifact.research_case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Research case not found")
        claims = await store.list_claims(case.id)
        claim_forms = []
        for claim in claims:
            evidence = await store.list_claim_evidence(claim.id)
            evidence_forms = "".join(
                f'<li>{html.escape(link.evidence.passage_text if link.evidence else "")} '
                f'<span class="pill">{html.escape(link.stance)}</span><form method="post" '
                f'action="/app/reviews/{review_id}/evidence"><input type="hidden" name="claim_id" value="{claim.id}">'
                f'<input type="hidden" name="evidence_id" value="{link.evidence_passage_id}">'
                '<input name="reason" placeholder="Decision reason" required><button name="decision" value="evidence_accepted">Accept</button>'
                '<button class="danger" name="decision" value="evidence_rejected">Reject</button></form></li>'
                for link in evidence
            ) or "<li>No evidence linked.</li>"
            claim_forms.append(
                f'<details><summary>C{claim.id}: {html.escape(claim.claim_text)} '
                f'<span class="pill">{html.escape(claim.verification_status)}</span></summary><ul>{evidence_forms}</ul>'
                f'<form method="post" action="/app/reviews/{review_id}/claims"><input type="hidden" name="claim_id" value="{claim.id}">'
                '<select name="status"><option>supported</option><option>qualified</option><option>disputed</option>'
                '<option>contradicted</option><option>unverifiable</option></select><input name="reason" placeholder="Correction reason" required>'
                '<button>Change status</button></form></details>'
            )
        sources = await store.list_research_case_sources(case.id)
        source_html = "".join(
            f"<li>{_safe_link(item.get('url'), item.get('title') or 'Source')} "
            f"<small>{html.escape(item.get('source_quality_rationale') or '')}</small></li>"
            for item in sources
        )
        return _page(
            f"Review {review_id}",
            f'<p class="pill">{html.escape(review_job.status)}</p><h1>Review: {html.escape(artifact.title)}</h1>'
            f'<p>Original input: {_safe_link(case.original_input, case.original_input)}</p>'
            f'<pre class="artifact">{html.escape(artifact.content)}</pre><section class="grid"><div class="card">'
            f'<h2>Claims and evidence</h2>{"".join(claim_forms)}</div><div class="card"><h2>Sources</h2><ul>{source_html}</ul>'
            f'<h2>Finalize</h2><form method="post" action="/app/reviews/{review_id}/finalize">'
            '<label>Review minutes</label><input name="review_minutes" type="number" min="0" step=".1" required>'
            '<button>Approve delivery</button></form></div></section>',
        )

    @router.post("/app/reviews/{review_id}/claims")
    async def review_claim(review_id: int, request: Request):
        reviewer_id = reviewer(request)
        values = await _form(request)
        await record_review_decision(
            request.app.state.store,
            review_id=review_id,
            reviewer_id=reviewer_id,
            entity_type="claim",
            entity_id=values.get("claim_id", ""),
            decision_type="claim_status_changed",
            new_value=values.get("status"),
            reason=values.get("reason", ""),
        )
        return RedirectResponse(f"/app/reviews/{review_id}", status_code=303)

    @router.post("/app/reviews/{review_id}/evidence")
    async def review_evidence(review_id: int, request: Request):
        reviewer_id = reviewer(request)
        values = await _form(request)
        await record_review_decision(
            request.app.state.store,
            review_id=review_id,
            reviewer_id=reviewer_id,
            entity_type="evidence",
            entity_id=values.get("evidence_id", ""),
            decision_type=values.get("decision", "evidence_rejected"),
            new_value={"claim_id": values.get("claim_id")},
            reason=values.get("reason", ""),
        )
        return RedirectResponse(f"/app/reviews/{review_id}", status_code=303)

    @router.post("/app/reviews/{review_id}/finalize")
    async def finalize_page(review_id: int, request: Request):
        reviewer_id = reviewer(request)
        values = await _form(request)
        await finalize_review(
            request.app.state.store,
            review_id=review_id,
            reviewer_id=reviewer_id,
            review_minutes=float(values.get("review_minutes") or 0),
            settings=settings,
        )
        return RedirectResponse("/app/reviews", status_code=303)

    return router
