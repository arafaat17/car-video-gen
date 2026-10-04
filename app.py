import asyncio
import os
import textwrap
import edge_tts
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# --- 1. CONFIGURATION & VOICE REGISTRY ---
VOICE_REGISTRY = {
    "Prabhat (Male)": {
        "voice": "en-IN-PrabhatNeural",
        "intro": "intro_male.mp4",
    },
    "Neerja (Female)": {
        "voice": "en-IN-NeerjaNeural",
        "intro": "intro_female.mp4",
    },
}

TARGET_SIZE = (1080, 1920)  # 9:16 Vertical Resolution


# --- 2. CAPTION & IMAGE PROCESSING HELPERS ---
def create_caption_overlay(
    size=TARGET_SIZE, text="", font_size=42, max_chars_per_line=28
):
    """Creates a transparent 1080x1920 overlay with a translucent caption banner at the bottom."""
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    if not text.strip():
        return overlay

    draw = ImageDraw.Draw(overlay)
    wrapped_text = textwrap.fill(text, width=max_chars_per_line)

    # Try standard system fonts (Mac / Linux / Fallback)
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size
        )
    except Exception:
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Helvetica.ttc", font_size
            )
        except Exception:
            font = ImageFont.load_default()

    # Calculate text dimensions
    text_bbox = draw.textbbox((0, 0), wrapped_text, font=font, align="center")
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    padding_x, padding_y = 30, 20
    box_w = text_w + (padding_x * 2)
    box_h = text_h + (padding_y * 2)

    # Center horizontally near the bottom (Y = 1520)
    box_x1 = (size[0] - box_w) // 2
    box_y1 = 1520
    box_x2 = box_x1 + box_w
    box_y2 = box_y1 + box_h

    # Draw dark translucent rounded banner
    draw.rounded_rectangle(
        [box_x1, box_y1, box_x2, box_y2], radius=18, fill=(0, 0, 0, 200)
    )

    # Draw white centered text
    draw.multiline_text(
        (box_x1 + padding_x, box_y1 + padding_y),
        wrapped_text,
        font=font,
        fill=(255, 255, 255, 255),
        align="center",
    )

    return overlay


def process_image_to_916(
    image_path, caption_text="", target_size=TARGET_SIZE
):
    """Pads landscape car images on a 9:16 black canvas and overlays captions."""
    img = Image.open(image_path).convert("RGBA")
    img.thumbnail(target_size, Image.Resampling.LANCZOS)

    background = Image.new("RGBA", target_size, (0, 0, 0, 255))
    offset = (
        (target_size[0] - img.width) // 2,
        (target_size[1] - img.height) // 2,
    )
    background.paste(img, offset)

    # Apply caption layer if text is provided
    if caption_text:
        caption_layer = create_caption_overlay(
            size=target_size, text=caption_text
        )
        background = Image.alpha_composite(background, caption_layer)

    final_img = background.convert("RGB")
    padded_path = f"padded_{os.path.basename(image_path)}"
    final_img.save(padded_path)
    return padded_path


def split_text_into_chunks(text, num_chunks):
    """Splits the script into roughly equal word groups matching the photo count."""
    words = text.split()
    if not words or num_chunks <= 0:
        return [""] * num_chunks

    chunk_size = max(1, len(words) // num_chunks)
    chunks = []
    for i in range(num_chunks):
        if i == num_chunks - 1:
            chunks.append(" ".join(words[i * chunk_size :]))
        else:
            chunks.append(
                " ".join(words[i * chunk_size : (i + 1) * chunk_size])
            )
    return chunks


# --- 3. TTS GENERATION HELPERS ---
async def generate_voiceover_async(text, voice, output_path="car_voice.mp3"):
    communicate = edge_tts.Communicate(text, voice, rate="+18%")
    await communicate.save(output_path)


def generate_voiceover(text, voice, output_path="car_voice.mp3"):
    asyncio.run(generate_voiceover_async(text, voice, output_path))


# --- 4. VIDEO ASSEMBLY ---
def build_final_video(
    intro_path,
    car_script,
    voiceover_path="car_voice.mp3",
    image_paths=[],
    output_path="final_car_reel.mp4",
):
    # 1. Load Intro Clip & Overlay Intro Captions
    intro_clip = VideoFileClip(intro_path)
    intro_caption_text = (
        "Welcome to S Cube Motors! Let's take a closer look at today's car deal."
    )

    intro_caption_img = create_caption_overlay(
        size=TARGET_SIZE, text=intro_caption_text
    )
    intro_caption_path = "temp_intro_caption.png"
    intro_caption_img.save(intro_caption_path)

    intro_caption_clip = ImageClip(intro_caption_path).set_duration(
        intro_clip.duration
    )
    intro_clip_with_caption = CompositeVideoClip(
        [intro_clip, intro_caption_clip]
    )

    # 2. Load Generated Narration Audio
    slideshow_audio = AudioFileClip(voiceover_path)
    slideshow_duration = slideshow_audio.duration

    # 3. Chunk Script & Process Car Photos
    num_images = len(image_paths)
    script_chunks = split_text_into_chunks(car_script, num_images)

    padded_image_paths = []
    for img_path, chunk_text in zip(image_paths, script_chunks):
        padded_path = process_image_to_916(img_path, caption_text=chunk_text)
        padded_image_paths.append(padded_path)

    img_duration = slideshow_duration / num_images

    # 4. Build Slideshow Sequence
    slideshow_clips = [
        ImageClip(p).set_duration(img_duration) for p in padded_image_paths
    ]
    slideshow_video = concatenate_videoclips(
        slideshow_clips, method="compose"
    ).set_audio(slideshow_audio)

    # 5. Combine Intro + Car Slideshow
    final_reel = concatenate_videoclips(
        [intro_clip_with_caption, slideshow_video], method="compose"
    )

    # 6. Render Output Video
    final_reel.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
    )

    # Cleanup Temporary Files
    if os.path.exists(intro_caption_path):
        os.remove(intro_caption_path)
    for p in padded_image_paths:
        if os.path.exists(p):
            os.remove(p)


# --- 5. STREAMLIT UI LAYOUT ---
st.set_page_config(
    page_title="S Cube Motors - Reel Generator", layout="centered"
)
st.title("🚗 S Cube Motors - Video Reel Generator")

presenter_choice = st.radio(
    "Select AI Presenter:", options=list(VOICE_REGISTRY.keys()), horizontal=True
)

car_script = st.text_area(
    "Car Details Script (Do NOT include 'Welcome to S Cube Motors'):",
    value="Check out this new-shape 2013 Chevrolet Cruze LTZ manual diesel. This second-owner sedan features a sunroof, push-button start, and Delphi engine with one lakh kilometers. Perfectly maintained with no work needed for just 2,20,000 rupees. Message us today!",
    height=120,
)

uploaded_files = st.file_uploader(
    "Upload Car Images (JPG/PNG):",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if st.button("Generate Video Reel", type="primary"):
    if not car_script.strip():
        st.error("Please enter a car script.")
    elif not uploaded_files:
        st.error("Please upload at least one car image.")
    else:
        selected_config = VOICE_REGISTRY[presenter_choice]
        intro_file = selected_config["intro"]
        voice_model = selected_config["voice"]

        if not os.path.exists(intro_file):
            st.error(
                f"Presenter video file '{intro_file}' not found in directory!"
            )
        else:
            with st.spinner("Processing video generation with captions..."):
                temp_img_paths = []
                for idx, file in enumerate(uploaded_files):
                    temp_path = f"temp_upload_{idx}.jpg"
                    with open(temp_path, "wb") as f:
                        f.write(file.read())
                    temp_img_paths.append(temp_path)

                try:
                    st.info(f"Generating voiceover using {presenter_choice}...")
                    generate_voiceover(
                        car_script, voice_model, output_path="car_voice.mp3"
                    )

                    st.info("Rendering vertical video reel with captions...")
                    build_final_video(
                        intro_path=intro_file,
                        car_script=car_script,
                        voiceover_path="car_voice.mp3",
                        image_paths=temp_img_paths,
                        output_path="final_car_reel.mp4",
                    )

                    st.success("Video generated successfully!")
                    st.video("final_car_reel.mp4")

                except Exception as e:
                    st.error(f"Error during video generation: {str(e)}")

                finally:
                    for p in temp_img_paths:
                        if os.path.exists(p):
                            os.remove(p)
                    if os.path.exists("car_voice.mp3"):
                        os.remove("car_voice.mp3")