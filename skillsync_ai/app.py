from __future__ import annotations

from http.server import ThreadingHTTPServer

from .web.server import create_server


def create_app(host: str = "127.0.0.1", port: int = 5050) -> ThreadingHTTPServer:
    return create_server(host=host, port=port)


def main() -> None:
    server = create_app()
    print("Serving MyCareer Compass at http://127.0.0.1:5050")
    server.serve_forever()


if __name__ == "__main__":
    main()
