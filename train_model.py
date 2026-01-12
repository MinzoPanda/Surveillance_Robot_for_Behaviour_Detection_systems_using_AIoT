from ultralytics import YOLO
import torch

if __name__ == '__main__':
    # 1. Clear any leftover memory from previous crashes
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    model = YOLO('yolov8n.pt')

    # 2. Start training with "Safe" settings
    model.train(
        data='C:/Users/Minzo/Desktop/Loitering.v1i.yolov8/data.yaml',
        epochs=30,
        imgsz=416,     # Reduced from 640 to 416 (uses much less RAM)
        batch=2,       # Only process 2 images at a time (default is 16)
        workers=0,     # Standard fix for Windows crashes (disables extra processes)
        device='cpu',  # Stick to CPU for now to ensure it doesn't crash your GPU
        cache=False    # Don't try to store the whole dataset in RAM
    )