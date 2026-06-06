import os
from PIL import Image
from core.tool_registry import aria_tool

class MediaConverter:
    @aria_tool(name="convert_image", description="Converts, resizes, or rotates an image. target_format: 'png', 'jpeg', 'webp'. resize_pct: scale percentage (e.g. 50). rotate_deg: rotation in degrees.")
    async def convert_image(self, filepath: str, target_format: str, resize_pct: int = 100, rotate_deg: int = 0) -> str:
        if not os.path.exists(filepath):
            return f"Error: Source image not found at {filepath}"
            
        try:
            img = Image.open(filepath)
            
            # Apply rotation
            if rotate_deg != 0:
                img = img.rotate(rotate_deg, expand=True)
                
            # Apply resizing
            if resize_pct != 100 and resize_pct > 0:
                width, height = img.size
                new_width = int(width * (resize_pct / 100))
                new_height = int(height * (resize_pct / 100))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
            # Determine target filename
            base_dir = os.path.dirname(filepath)
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            fmt = target_format.lower().strip('.')
            if fmt == 'jpg':
                fmt = 'jpeg'
            
            output_ext = 'jpg' if fmt == 'jpeg' else fmt
            output_path = os.path.join(base_dir, f"{base_name}_converted.{output_ext}")
            
            # If converting to JPEG, discard alpha channel
            if fmt == 'jpeg' and img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
                
            img.save(output_path, format=fmt.upper())
            return f"Image successfully processed and saved to: {output_path}"
        except Exception as e:
            return f"Image conversion failed: {str(e)}"

    @aria_tool(name="convert_pdf_to_images", description="Renders pages of a PDF document into PNG images. Returns the list of output image file paths.")
    async def convert_pdf_to_images(self, pdf_path: str, output_dir: str = "") -> str:
        if not os.path.exists(pdf_path):
            return f"Error: PDF file not found at {pdf_path}"
            
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            
            if not output_dir:
                output_dir = os.path.dirname(pdf_path) or "."
            os.makedirs(output_dir, exist_ok=True)
            
            pdf_base = os.path.splitext(os.path.basename(pdf_path))[0]
            output_paths = []
            
            for i in range(len(doc)):
                page = doc[i]
                pix = page.get_pixmap(dpi=150)
                out_path = os.path.join(output_dir, f"{pdf_base}_page_{i+1}.png")
                pix.save(out_path)
                output_paths.append(out_path)
                
            doc.close()
            return f"Successfully rendered {len(output_paths)} pages. Image paths:\n" + "\n".join(output_paths)
        except Exception as e:
            return f"PDF rendering failed: {str(e)}"

    @aria_tool(name="create_pdf_from_images", description="Combines a list of image file paths into a single PDF document.")
    async def create_pdf_from_images(self, image_paths: list, output_pdf_path: str) -> str:
        if not image_paths:
            return "Error: No image paths provided."
            
        try:
            images = []
            for path in image_paths:
                if not os.path.exists(path):
                    return f"Error: Image not found at {path}"
                img = Image.open(path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
                
            os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
            images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
            return f"PDF document compiled successfully to: {output_pdf_path}"
        except Exception as e:
            return f"PDF compilation failed: {str(e)}"

    @aria_tool(name="extract_video_frame", description="Extracts a frame from a video file at the specified timestamp in seconds and saves it as an image.")
    async def extract_video_frame(self, video_path: str, timestamp_sec: float, output_path: str = "") -> str:
        if not os.path.exists(video_path):
            return f"Error: Video file not found at {video_path}"
            
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return f"Error: Could not open video file {video_path}"
                
            # Seek to timestamp
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000)
            success, frame = cap.read()
            cap.release()
            
            if not success:
                return f"Error: Failed to read frame at {timestamp_sec} seconds."
                
            if not output_path:
                video_dir = os.path.dirname(video_path) or "."
                video_base = os.path.splitext(os.path.basename(video_path))[0]
                output_path = os.path.join(video_dir, f"{video_base}_frame_{timestamp_sec:.2f}.png")
                
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            cv2.imwrite(output_path, frame)
            return f"Video frame extracted and saved to: {output_path}"
        except Exception as e:
            return f"Video frame extraction failed: {str(e)}"

media_converter = MediaConverter()
