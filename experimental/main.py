from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import librosa
import logging
import os
import shutil
import json


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS config so frontend can talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    bar_lengths = {}
    for file in files:
        path = os.path.join(UPLOAD_DIR, file.filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        try:
            y, sr = librosa.load(path)
            duration = librosa.get_duration(y=y, sr=sr)
            bpm = 120  # Set your default BPM here
            seconds_per_beat = 60 / bpm
            beats = duration / seconds_per_beat
            bars = int(beats // 4)  # Assuming 4 beats/bar
            bar_lengths[file.filename.replace(".wav", "")] = bars
            logger.info(f"Processed {file.filename}: {bars} bars")
            logger.info(bar_lengths)
        except Exception as e:
            bar_lengths[file.filename.replace(".wav", "")] = 0
            logger.error(f"Error processing {file.filename}: {e}")
    # Clean up uploaded files
    for file in files:
        path = os.path.join(UPLOAD_DIR, file.filename)
        if os.path.exists(path):
            os.remove(path)
    return JSONResponse(content=bar_lengths)


@app.post("/analyze_bars")
async def analyze_bars(files: List[UploadFile] = File(...)):
    bar_data = {}
    for file in files:
        path = os.path.join(UPLOAD_DIR, file.filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        try:
            y, sr = librosa.load(path)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            bpm = 120  # Default BPM
            seconds_per_beat = 60 / bpm
            bars = {}
            for beat_time in beat_times:
                bar_number = int(beat_time // (seconds_per_beat * 4)) + 1
                if bar_number not in bars:
                    bars[bar_number] = []
                bars[bar_number].append(round(beat_time, 2))

            bar_data[file.filename.replace(".wav", "")] = bars
            logger.info(f"Analyzed {file.filename}: {bars}")
        except Exception as e:
            bar_data[file.filename.replace(".wav", "")] = {}
            logger.error(f"Error analyzing {file.filename}: {e}")
    # Clean up uploaded files
    for file in files:
        path = os.path.join(UPLOAD_DIR, file.filename)
        if os.path.exists(path):
            os.remove(path)
    return JSONResponse(content=bar_data)


@app.post("/render")
async def render_audio(active_map: dict):
    # TODO: Mix logic goes here
    return FileResponse("uploads/sample.wav", media_type="audio/wav")


@app.post("/save_arrangement")
async def save_arrangement(data: dict):
    with open("arrangement.json", "w") as f:
        json.dump(data, f, indent=2)
    return {"status": "Arrangement saved"}


if __name__ == "__main__":
    import uvicorn

    # Run the app with uvicorn
    uvicorn.run(app, host="localhost", port=8000)
