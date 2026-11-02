import uvicorn

from app.core.config import load_settings

if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload,
        log_level=settings.log_level,
    )
