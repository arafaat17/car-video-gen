import asyncio
import os
import tempfile
import textwrap
import edge_tts
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# MoviePy 1.0.3 imports
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx
)

# -----------------------------------------------------------------------------
# 1. Page Configuration & Custom CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="S Cube Motors - Reel Studio",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* Gradient Main Header */
    .hero-title {
        background: linear-gradient(90deg, #FF4B4B, #FF8F00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.6rem;
        margin-bottom: 0px;
    }
    
    .hero-subtitle {
        color: #A0AAB8;
        font-size: 1.1rem;
        margin-bottom: 15px;
    }

    /* Custom Feature Badges */
    .badge {
        background-color: #1E2638;
        color: #00E676;
        padding: 5px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
        border: 1px solid #2E3B52;
        margin-right: 8px;
        display: inline-block;
    }

    /* Primary Action Button */
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #FF4B4B 0%, #FF2A2A 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        font-size: 1.1rem;
        font-weight: bold;
        border-radius: 8px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 75, 75, 0.5);
    }
    </style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. Helper Functions
# -----------------------------------------------------------------------------
async def generate_tts_audio(text: str, voice: str, output_path: str):
    """Generates TTS audio file using edge-tts."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def process_image_to_916(image_file, target_size=(1080, 1920)):
    """Resizes and pads an image to fit 9:16 aspect ratio (1080x1920)."""
    img = Image.open(image_file).convert("RGB")
    bg = Image.new("RGB", target_size, (15, 15, 15))
    img.thumbnail(target_size, Image.Resampling.LANCZOS)
    x = (target_size[0] - img.width) // 2
    y = (target_size[1] - img.height) // 2
    bg.paste(img, (x, y))
    return bg


def add_caption_to_image(pil_img, text, font_size=38):
    """Draws caption banner at bottom of image."""
    img_copy = pil_img.copy().convert("RGBA")
    w, h = img_copy.size

    banner_height = 180
    banner_y = h - banner_height - 120
    
    overlay = Image.new("RGBA", img_copy.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [(40, banner_y), (w - 40, banner_y + banner_height)],
        fill=(0, 0, 0, 210),
        outline=(255, 75, 75, 255),
        width=3
    )

    img_copy = Image.alpha_composite(img_copy, overlay).convert("RGB")
    draw = ImageDraw.Draw(img_copy)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    lines = textwrap.wrap(text, width=32)
    line_y = banner_y + 20
    
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        text_x = (w - text_w) // 2
        draw.text((text_x, line_y), line, fill=(255, 255, 255), font=font)
        line_y += font_size + 12

    return img_copy


def build_video_reel(presenter_choice, script_text, media_mode, uploaded_images, uploaded_video, status_box):
    """Full pipeline: Audio TTS -> Media Clip -> Video Stitching."""
    
    if "Neerja" in presenter_choice:
        voice = "en-IN-NeerjaNeural"
        intro_filename = "intro_female.mp4"
    else:
        voice = "en-IN-PrabhatNeural"
        intro_filename = "intro_male.mp4"

    with tempfile.TemporaryDirectory() as temp_dir:
        # Step 1: Generate AI Audio
        status_box.text("🎙️ Generating AI voiceover...")
        audio_path = os.path.join(temp_dir, "speech.mp3")
        asyncio.run(generate_tts_audio(script_text, voice, audio_path))

        speech_audio = AudioFileClip(audio_path)
        audio_duration = speech_audio.duration

        # Step 2: Handle Media Input
        if media_mode == "Upload Photos (Slideshow)":
            status_box.text("🖼️ Processing images & dynamic captions...")
            num_images = len(uploaded_images)
            img_duration = max(2.5, audio_duration / num_images)

            img_clips = []
            for idx, file in enumerate(uploaded_images):
                padded_img = process_image_to_916(file)
                captioned_img = add_caption_to_image(padded_img, script_text)
                
                proc_path = os.path.join(temp_dir, f"img_{idx}.png")
                captioned_img.save(proc_path)

                clip = ImageClip(proc_path).set_duration(img_duration)
                img_clips.append(clip)

            main_clip = concatenate_videoclips(img_clips, method="compose")
            main_clip = main_clip.set_audio(speech_audio)

        else:
            # Video Upload mode
            status_box.text("📹 Syncing AI voiceover to custom video...")
            video_input_path = os.path.join(temp_dir, "user_video.mp4")
            with open(video_input_path, "wb") as f:
                f.write(uploaded_video.read())

            custom_clip = VideoFileClip(video_input_path)
            
            # Ensure video is 1080x1920 vertical format
            custom_clip = custom_clip.resize((1080, 1920))

            # Match video length to AI voiceover length
            if custom_clip.duration < audio_duration:
                custom_clip = custom_clip.fx(vfx.loop, duration=audio_duration)
            else:
                custom_clip = custom_clip.subclip(0, audio_duration)

            # Set AI speech audio onto custom video
            main_clip = custom_clip.set_audio(speech_audio)

        # Step 3: Stitch Intro Presenter + Main Clip
        status_box.text("🎬 Stitching intro presenter & car clip...")
        if os.path.exists(intro_filename):
            intro_clip = VideoFileClip(intro_filename)
            intro_clip = intro_clip.resize((1080, 1920))
            final_clip = concatenate_videoclips([intro_clip, main_clip], method="compose")
        else:
            final_clip = main_clip

        # Step 4: Render Final Video
        status_box.text("⚡ Rendering final HD reel...")
        output_file = os.path.join(temp_dir, "final_reel.mp4")
        
        final_clip.write_videofile(
            output_file,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=os.path.join(temp_dir, "temp-audio.m4a"),
            remove_temp=True,
            logger=None
        )

        with open(output_file, "rb") as vf:
            video_bytes = vf.read()

        return video_bytes


# -----------------------------------------------------------------------------
# 3. Application UI
# -----------------------------------------------------------------------------
st.markdown('<h1 class="hero-title">🏎️️ S Cube Motors</h1>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtitle">Automated AI Video Reel Generator</p>', unsafe_allow_html=True)

st.markdown("""
    <span class="badge">⚡ Instant AI Voice</span>
    <span class="badge">📱 9:16 Reel Format</span>
    <span class="badge">🎬 Dynamic Auto-Captions</span>
    <br><br>
""", unsafe_allow_html=True)

st.divider()

col1, col2 = st.columns([1.2, 0.8], gap="large")

with col1:
    st.subheader("🛠️ Configuration")
    
    with st.container(border=True):
        st.markdown("**1. Select AI Presenter**")
        presenter = st.radio(
            "Choose Presenter",
            ["Prabhat (Male)", "Neerja (Female)"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.markdown("**2. Car Details Script** *(Excludes 'Welcome to S Cube Motors')*")
        script_input = st.text_area(
            "Script",
            value="",
            placeholder="e.g. Check out this 2013 Chevrolet Cruze LTZ manual diesel. Second owner, sunroof, push-button start, 1,00,000 km. Priced at 2.2 Lakhs. Contact us today!",
            height=130,
            label_visibility="collapsed"
        )
        
        st.markdown("**3. Select Media Mode**")
        media_mode = st.radio(
            "Media Type",
            ["Upload Photos (Slideshow)", "Upload Custom Video"],
            horizontal=True,
            label_visibility="collapsed"
        )

        uploaded_images = None
        uploaded_video = None

        if media_mode == "Upload Photos (Slideshow)":
            st.markdown("**Upload Car Photos (JPG/PNG)**")
            uploaded_images = st.file_uploader(
                "Upload Images",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                label_visibility="collapsed"
            )
        else:
            st.markdown("**Upload Pre-edited Video (MP4/MOV)**")
            uploaded_video = st.file_uploader(
                "Upload Video",
                type=["mp4", "mov", "m4v"],
                accept_multiple_files=False,
                label_visibility="collapsed"
            )
        
        st.markdown("---")
        generate_clicked = st.button("🚀 Generate Studio Reel")

with col2:
    st.subheader("📺 Output Preview")
    
    output_container = st.container(border=True)
    
    with output_container:
        if generate_clicked:
            if media_mode == "Upload Photos (Slideshow)" and not uploaded_images:
                st.warning("⚠️ Please upload at least one car image.")
            elif media_mode == "Upload Custom Video" and not uploaded_video:
                st.warning("⚠️ Please upload a custom video file.")
            elif not script_input.strip():
                st.warning("⚠️ Please enter a car details script.")
            else:
                status = st.empty()
                progress_bar = st.progress(0)
                
                try:
                    progress_bar.progress(25)
                    video_data = build_video_reel(
                        presenter,
                        script_input,
                        media_mode,
                        uploaded_images,
                        uploaded_video,
                        status
                    )
                    progress_bar.progress(100)
                    
                    status.success("🎉 Reel Generated Successfully!")
                    st.video(video_data)
                    
                    st.download_button(
                        label="📥 Download Video Reel",
                        data=video_data,
                        file_name="s_cube_motors_reel.mp4",
                        mime="video/mp4"
                    )
                except Exception as e:
                    status.error(f"❌ Generation failed: {str(e)}")
                    progress_bar.empty()
        else:
            st.markdown(
                """
                <div style="text-align: center; padding: 50px 20px; color: #6C757D;">
                    <p style="font-size: 3.5rem; margin-bottom: 10px;">🎬</p>
                    <p style="font-size: 1.05rem;">Configure settings on the left and click <b>Generate Studio Reel</b> to view your video here.</p>
                </div>
                """,
                unsafe_allow_html=True
            )