from app.api import create_app
from app.routes import router

app = create_app(router, handler=None)
