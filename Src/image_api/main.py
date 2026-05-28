import os
import shutil
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

from PIL import Image as PILImage


DATABASE_URL = "sqlite:///./images.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


class ImageMetadata(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    size = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    file_type = Column(String)
    date_added = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String)


Base.metadata.create_all(bind=engine)


app = FastAPI(title="Image API")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/api/image/add")
async def add_image(file: UploadFile = File(...)):
    db = SessionLocal()

    file_ext = file.filename.split(".")[-1]
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        with PILImage.open(file_path) as img:
            width, height = img.size
    except Exception:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Некорректное изображение")

    file_size = os.path.getsize(file_path)

    db_image = ImageMetadata(
        name=file.filename,
        size=file_size,
        width=width,
        height=height,
        file_type=file_ext,
        file_path=file_path
    )

    db.add(db_image)
    db.commit()
    db.close()

    return {"message": "Изображение сохранено"}


@app.put("/api/image/change/color")
async def change_color(image_path: str):
    with PILImage.open(image_path) as img:
        bw_img = img.convert("L")
        bw_img.save(image_path)

    return {"message": "Изображение стало черно-белым"}


@app.put("/api/image/change/path")
async def move_image(image_path: str, new_dir: str):
    os.makedirs(new_dir, exist_ok=True)

    filename = os.path.basename(image_path)
    new_path = os.path.join(new_dir, filename)

    shutil.move(image_path, new_path)

    return {"message": "Изображение перемещено"}


@app.get("/api/image")
async def get_images():
    db = SessionLocal()
    images = db.query(ImageMetadata).all()
    db.close()
    return images


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
    <body>
        <h1>Image API</h1>

        <input type="file" id="fileInput">
        <button onclick="uploadImage()">Загрузить</button>
        <button onclick="loadImages()">Показать</button>

        <div id="gallery"></div>

        <script>
            async function uploadImage() {
                const fileInput = document.getElementById('fileInput');

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);

                await fetch('/api/image/add', {
                    method: 'POST',
                    body: formData
                });

                loadImages();
            }

            async function loadImages() {
                let res = await fetch('/api/image');
                let images = await res.json();

                let gallery = document.getElementById('gallery');
                gallery.innerHTML = '';

                images.forEach(img => {
                    gallery.innerHTML += `
                        <div>
                            <h3>${img.name}</h3>
                            <img src="/${img.file_path}" width="200">
                            <br>
                            <button onclick="makeBW('${img.file_path}')">
                                Ч/Б
                            </button>
                            <hr>
                        </div>
                    `;
                });
            }

            async function makeBW(path) {
                await fetch('/api/image/change/color?image_path=' + encodeURIComponent(path), {
                    method: 'PUT'
                });

                loadImages();
            }

            window.onload = loadImages;
        </script>
    </body>
    </html>
    """
