from app import app
from app.models import init_db

# Initialize database
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)