from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn


app = FastAPI()

# Serve the 'archives' directory statically
app.mount("/archives", StaticFiles(directory="archives"), name="archives")


if __name__ == "__main__":
    uvicorn.run("browse:app", host="127.0.0.1", port=4444, reload=True)