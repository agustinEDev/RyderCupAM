"""
Main entry point for the Ryder Cup Manager application.
"""
from fastapi import FastAPI

app = FastAPI(
    title="Ryder Cup Manager",
    description="API for managing Ryder Cup competitions",
    version="1.0.0"
)


@app.get("/")
async def root():
    return {"message": "Welcome to Ryder Cup Manager API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)