"""Run the local listener and open its interface only after startup succeeds."""
import socket
import webbrowser


def run_local_service(settings, port, *, open_browser=False):
    import uvicorn
    from markov_engine.api import create_app

    class DesktopServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            if self.started and open_browser:
                webbrowser.open(f'http://127.0.0.1:{port}/app')

    # Reserve the port before opening the archive or starting its worker.
    # A second launch must not start a second worker against the same listener.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', port))
        config = uvicorn.Config(create_app(settings=settings), host='127.0.0.1', port=port,
            proxy_headers=True, forwarded_allow_ips='127.0.0.1,::1', loop='asyncio',
            http='h11', ws='none', lifespan='on')
        DesktopServer(config).run(sockets=[listener])
