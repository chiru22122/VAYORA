import os
import sys
import uvicorn

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    from backend.config import BACKEND_URL, FRONTEND_URL

    print("=" * 60)
    print("  VAYORA - Your Digital Value, One Journey.")
    print("  Futuristic Fintech Platform & Digital Asset Hub")
    print(f"  Backend API:       {BACKEND_URL}")
    print(f"  Frontend Origin:   {FRONTEND_URL}")
    print(f"  API Documentation: {BACKEND_URL}/api/docs")
    print("=" * 60)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
