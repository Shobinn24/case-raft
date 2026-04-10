from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()

# Rate limiter — initialized in create_app(). Default limits are permissive;
# individual routes can apply tighter limits via @limiter.limit("...").
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)
