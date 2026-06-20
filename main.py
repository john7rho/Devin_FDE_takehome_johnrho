import os
import uvicorn
from app.api.main import app

if __name__ == "__main__":
    # Hosts (Render/Railway/Fly) inject the port via $PORT; default to 8000 locally.
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
