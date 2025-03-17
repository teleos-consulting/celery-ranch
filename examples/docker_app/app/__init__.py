from flask import Flask

from .config import Config

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Import routes at bottom to avoid circular imports
import examples.docker_app.app.routes  # noqa: E402, F401
