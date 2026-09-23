from os import environ, path
import hmac
import secrets

from dotenv import load_dotenv
from flask import Flask, abort, request, session
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

DB_NAME = "database.db"


def create_app(test_config=None):
    app = Flask(__name__)

    project_root = path.abspath(path.join(path.dirname(__file__), ".."))
    db_path = path.join(project_root, DB_NAME)

    app.config["SECRET_KEY"] = environ.get(
        "FLASK_SECRET_KEY", "dev-only-change-this-secret"
    )
    app.config["UPLOAD_FOLDER"] = path.join(project_root, "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    app.config["SQLALCHEMY_DATABASE_URI"] = environ.get("DATABASE_URL", f"sqlite:///{db_path}")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models before schema creation.
    from .models import (
        ClassChatMessage,
        ClassPost,
        ClassRoom,
        Comment,
        Message,
        Note,
        NoteAttachment,
        NoteHistory,
        Poll,
        PollOption,
        PollVote,
        Reaction,
        Tag,
        User,
    )

    from .admin import admin
    from .auth import auth
    from .views import views

    app.register_blueprint(views, url_prefix="/")
    app.register_blueprint(auth, url_prefix="/")
    app.register_blueprint(admin, url_prefix="/admin")

    def generate_csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    @app.before_request
    def csrf_protect():
        if app.config.get("TESTING") or request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            return None
        expected = session.get("_csrf_token")
        provided = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not expected or not provided or not hmac.compare_digest(expected, provided):
            abort(400, description="Invalid or missing CSRF token")
        return None

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self' data: blob:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://code.jquery.com https://cdn.quilljs.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdn.quilljs.com; "
            "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob: https://*; "
            "connect-src 'self';",
        )
        return response

    @app.errorhandler(400)
    def bad_request(_error):
        from flask import render_template
        return render_template("error.html", code=400, title="Bad request", message="The request could not be verified or was malformed."), 400

    @app.errorhandler(404)
    def not_found(_error):
        from flask import render_template
        return render_template("error.html", code=404, title="Page not found", message="The page you requested does not exist."), 404

    @app.errorhandler(413)
    def too_large(_error):
        from flask import render_template
        return render_template("error.html", code=413, title="File too large", message="Uploads are limited to 10 MB."), 413

    @app.errorhandler(500)
    def server_error(_error):
        from flask import render_template
        db.session.rollback()
        return render_template("error.html", code=500, title="Something went wrong", message="The request could not be completed."), 500

    return app
