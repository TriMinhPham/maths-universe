"""Standalone loopback-only Firstbot browser adventure (no robot or cloud).

Run: PYTHONPATH=laptop python3 laptop/adventure_app.py --host 127.0.0.1 --port 8770
Parent controls trust local laptop access; they are not password authentication.
"""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from adventure_store import AdventureStore, Conflict, DEFAULT_DB

ASSETS = Path(__file__).resolve().parent
MAX_BODY = 16384


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not accepted')
        result[key] = value
    return result


def create_app(db_path=DEFAULT_DB, quest_bank=None, quest_partial=False):
    store = AdventureStore(db_path)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            store.close()

    app = FastAPI(title='Firstbot Maths Adventure', docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.store = store

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def invalid_handler(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        def denied(message, status=403):
            return JSONResponse({'detail': message}, status_code=status)
        hosts = request.headers.getlist('host')
        if len(hosts) != 1:
            return denied('Exactly one loopback Host is required')
        host = hosts[0]
        try:
            parsed = urlsplit('http://' + host)
            if (parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username is not None
                    or parsed.password is not None or parsed.path or parsed.query or parsed.fragment
                    or any(c.isspace() for c in host) or '\\' in host):
                return denied('Only a loopback Host is allowed')
            port = parsed.port or 80
            server = request.scope.get('server')
            if server and server[1] and port != server[1]:
                return denied('Host port must match this local server')
        except ValueError:
            return denied('Invalid Host')
        if request.client:
            try:
                if not ipaddress.ip_address(request.client.host).is_loopback:
                    return denied('Only loopback clients are allowed')
            except ValueError:
                return denied('Only loopback clients are allowed')
        origins = request.headers.getlist('origin')
        if origins and (len(origins) != 1 or origins[0] != request.url.scheme + '://' + host):
            return denied('Origin must match this local application')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return denied('Cross-site requests are not allowed')
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
                return denied('Mutations require application/json', 400)
            try:
                length = int(request.headers.get('content-length', '0'))
                if length < 0 or length > MAX_BODY:
                    return denied('Request body is too large', 400)
            except ValueError:
                return denied('Invalid Content-Length', 400)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        )
        return response

    @app.get('/health')
    def health():
        return {'ok': True, 'app': 'Firstbot Maths Adventure', 'mode': 'separate-browser-progress'}

    full_bank = Path(quest_bank) if quest_bank else ASSETS / 'full_math_lessons.json'
    quests_enabled = full_bank.exists()
    if quests_enabled:
        from full_math_app import install
        install(app, store, full_bank, require_complete=not quest_partial)

    @app.get('/')
    def index():
        return FileResponse(ASSETS / ('full_math.html' if quests_enabled else 'adventure.html'), media_type='text/html')

    @app.get('/starter')
    def starter():
        return FileResponse(ASSETS / 'adventure.html', media_type='text/html')

    @app.get('/adventure.js')
    def javascript():
        return FileResponse(ASSETS / 'adventure.js', media_type='text/javascript')

    @app.get('/adventure.css')
    def stylesheet():
        return FileResponse(ASSETS / 'adventure.css', media_type='text/css')

    @app.get('/licenses/{name}')
    def license_file(name: str):
        if name not in {'LICENSE', 'LICENSE-CONTENT', 'PROVENANCE.md', 'NOTICE.md'}:
            return JSONResponse({'detail': 'Not found'}, status_code=404)
        return FileResponse(ASSETS / 'vendor/os-taxonomy' / name, media_type='text/plain')

    @app.get('/api/state')
    def state():
        return store.state()

    @app.get('/api/history')
    def history(request: Request):
        if any(key != 'before' for key in request.query_params) or len(request.query_params.getlist('before')) > 1:
            raise ValueError('Only one before history cursor is supported')
        before = request.query_params.get('before')
        if before is not None:
            if not before.isascii() or not before.isdecimal() or len(before) > 10:
                raise ValueError('Invalid history cursor')
            before = int(before)
        return store.history(before)

    # Explicit exact fields reject client-provided correctness and unexpected
    # settings. Integers/bools are checked strictly by AdventureStore, not coerced.
    operations = {
        'start': (store.start, {'stage_id', 'request_id'}, set()),
        'event': (store.event, {'problem_id', 'action', 'choice', 'request_id'}, set()),
        'next': (store.next, {'request_id'}, set()),
        'override': (store.override, {'stage_id', 'reason', 'request_id'}, set()),
        'stars': (store.adjust, {'reason'}, {'delta', 'total'}),
        'earning': (store.earning, {'auto', 'per_correct', 'reason'}, set()),
    }

    @app.post('/api/{operation}')
    async def mutate(operation: str, request: Request):
        if operation not in operations:
            return JSONResponse({'detail': 'Unknown operation'}, status_code=404)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_BODY:
                raise ValueError('Request body is too large')
        try:
            body = json.loads(bytes(raw), object_pairs_hook=_object,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON number')))
        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError('A valid JSON object is required') from exc
        function, required, optional = operations[operation]
        if type(body) is not dict or not required <= body.keys() or not body.keys() <= required | optional:
            raise ValueError('Exact supported request fields are required')
        return await run_in_threadpool(function, **body)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=8770, type=int)
    parser.add_argument('--db', default=str(DEFAULT_DB))
    args = parser.parse_args()
    try:
        if not ipaddress.ip_address(args.host).is_loopback:
            parser.error('--host must be a numeric loopback address')
    except ValueError:
        parser.error('--host must be a numeric loopback address')
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    import uvicorn
    uvicorn.run(create_app(args.db), host=args.host, port=args.port, proxy_headers=False)


if __name__ == '__main__':
    main()
