"""Bound request ingress before Starlette's multipart spooling stage."""
import re

from starlette.formparsers import MultiPartException

from src.files.parsers.base import MAX_FILE_BYTES


class UploadBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope['type'] != 'http' or scope['method'] != 'POST' or
                not re.fullmatch(r'/v1/artifacts/[^/]+/files/?', scope['path'])):
            await self.app(scope, receive, send)
            return
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            if message['type'] == 'http.request':
                total += len(message.get('body', b''))
                # Allow bounded multipart headers; the service independently
                # enforces exactly 50 MiB for the actual file stream.
                if total > MAX_FILE_BYTES + 1024 * 1024:
                    scope['source_body_limit_exceeded'] = True
                    # Multipart parser closes every partially spooled file when
                    # this exception is raised, then maps it to HTTPException.
                    raise MultiPartException('Upload request is too large.')
            return message

        await self.app(scope, bounded_receive, send)
