from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import json
import asyncio
import aiofiles
import shutil
import aiohttp
import edge_tts
import resend

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Vérifier et installer FFmpeg si nécessaire au démarrage
import subprocess

def ensure_ffmpeg_installed():
    """Vérifie que FFmpeg est installé, sinon l'installe"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg est disponible")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ FFmpeg non trouvé, installation en cours...")
        try:
            subprocess.run(['apt-get', 'update', '-qq'], check=True, capture_output=True)
            subprocess.run(['apt-get', 'install', '-y', '-qq', 'ffmpeg', 'imagemagick'],
                         check=True, capture_output=True)
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            print("✅ FFmpeg installé avec succès")
        except Exception as e:
            print(f"❌ ERREUR: Impossible d'installer FFmpeg: {e}")
            print("SOLUTION: Exécutez: apt-get update && apt-get install -y ffmpeg")

# Installer FFmpeg avant de démarrer
ensure_ffmpeg_installed()

mongo_url = os.environ.get('MONGO_URL')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME')]

UPLOAD_DIR = ROOT_DIR / "uploads"
OUTPUT_DIR = ROOT_DIR / "outputs"
ASSETS_DIR = ROOT_DIR / "assets"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Track cancelled projects
cancelled_projects = set()

# Microsoft Edge TTS Configuration (Free Neural Voices)
EDGE_TTS_VOICE_MALE = "fr-FR-HenriNeural"
EDGE_TTS_VOICE_FEMALE = "fr-FR-DeniseNeural"

# Resend Email Configuration
resend.api_key = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')


class VideoProject(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    progress: int = 0
    progress_message: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    image_paths: List[str] = []
    subtitles: List[str] = []
    duration_per_image: float = 5.0
    total_images: int = 0
    enable_voiceover: bool = False
    voice_gender: str = "male"
    hd_quality: bool = False
    background_music: Optional[str] = None
    transition_type: str = "zoomin"
    user_email: Optional[str] = None


class VideoProjectResponse(BaseModel):
    project_id: str
    status: str
    message: str
    total_images: int


class ProjectStatus(BaseModel):
    id: str
    status: str
    progress: int
    progress_message: str
    video_url: Optional[str] = None
    error_message: Optional[str] = None


def create_ass_subtitle(text: str, duration: float, output_path: Path):
    """Create ASS subtitle with fixed 600px black rectangle at 80% opacity, centered text with adaptive font"""
    # Si pas de texte, créer un fichier ASS vide (sans rectangle noir)
    if not text or not text.strip():
        ass_content = f"""[Script Info]
Title: Subtitle
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Text,Arial,50,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)
        return
    
    escaped_text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    
    # Fixed rectangle dimensions
    BOX_HEIGHT = 600  # ALWAYS 600px height
    BOX_WIDTH = 920   # Width with margins (1080 - 2*80)
    margin_h = 80     # Horizontal margin from edges
    margin_v = 110    # Vertical margin from bottom (80 + 30 = 110)
    
    # Box position (centered horizontally, positioned from bottom)
    box_center_x = 540  # Center of 1080px width
    box_center_y = 1920 - margin_v - (BOX_HEIGHT // 2)  # From bottom, center of box
    
    half_width = BOX_WIDTH // 2
    half_height = BOX_HEIGHT // 2
    
    # Calculate adaptive font size to fit text within 600px height
    text_length = len(text)
    max_chars_per_line = 35  # Estimated characters per line at base font size
    estimated_lines = max(1, int(text_length / max_chars_per_line) + 1)
    
    # Calculate font size to fit within 600px height
    # Available height = 600px - padding
    padding_vertical = 60  # Total vertical padding (top + bottom)
    available_height = BOX_HEIGHT - padding_vertical
    line_height_factor = 1.35  # Line height = font_size * factor
    
    # font_size * line_height_factor * estimated_lines = available_height
    calculated_font_size = available_height / (estimated_lines * line_height_factor)
    
    # Clamp font size between 28px (min) and 78px (max)
    font_size = int(max(28, min(78, calculated_font_size)))
    
    spacing = 0 if font_size >= 60 else -1
    
    # ASS color format: &HAABBGGRR where AA = transparency (00 = opaque, FF = transparent)
    # For 80% opacity = 20% transparency = 33 in hex
    
    ass_content = f"""[Script Info]
Title: Subtitle
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: BlackBox,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H33000000,1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Text,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,{spacing},0,1,3,1,5,{margin_h},{margin_h},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:{duration:.2f},BlackBox,,0,0,0,,{{\\pos({box_center_x},{box_center_y})\\p1\\c&H000000&\\alpha&H33&}}m -{half_width} -{half_height} l {half_width} -{half_height} {half_width} {half_height} -{half_width} {half_height}{{\\p0}}
Dialogue: 1,0:00:00.00,0:00:{duration:.2f},Text,,0,0,0,,{{\\pos({box_center_x},{box_center_y})}}{escaped_text}
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)


async def update_project_status(project_id: str, status: str = None, progress: int = None,
                                 progress_message: str = None, video_url: str = None,
                                 error_message: str = None):
    update_dict = {}
    if status is not None:
        update_dict["status"] = status
    if progress is not None:
        update_dict["progress"] = progress
    if progress_message is not None:
        update_dict["progress_message"] = progress_message
    if video_url is not None:
        update_dict["video_url"] = video_url
    if error_message is not None:
        update_dict["error_message"] = error_message
    if update_dict:
        await db.video_projects.update_one({"id": project_id}, {"$set": update_dict})


async def run_ffmpeg(cmd: List[str]) -> tuple:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode(), stderr.decode()


async def generate_voiceover(text: str, output_path: Path, voice_gender: str = "male") -> bool:
    """Generate voiceover using Microsoft Edge TTS (Free Neural Voices)"""
    try:
        if not text or not text.strip():
            return False
        
        voice = EDGE_TTS_VOICE_MALE if voice_gender == "male" else EDGE_TTS_VOICE_FEMALE
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(output_path))
        
        logger.info(f"Successfully generated voiceover with {voice}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating voiceover with Edge TTS: {str(e)}")
        return False


async def get_audio_duration(audio_path: Path) -> float:
    """Get duration of audio file using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return float(stdout.decode().strip())
    except Exception:
        return 0.0


async def send_download_email(email: str, project_id: str, download_url: str):
    """Send download link email to user"""
    try:
        if not email or not resend.api_key:
            return
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
            <h1 style="color:#F97316;">🎬 Votre vidéo est prête !</h1>
            <p>Bonjour,</p>
            <p>Votre vidéo HD a été générée avec succès par <strong>Afrique Résurrection</strong>.</p>
            <p style="margin:30px 0;">
                <a href="{download_url}" style="background:#F97316;color:white;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold;">
                    Télécharger ma vidéo
                </a>
            </p>
            <p style="color:#666;font-size:14px;">Ce lien est valable pendant 24 heures.</p>
            <hr style="border:none;border-top:1px solid #eee;margin:30px 0;">
            <p style="color:#999;font-size:12px;">© Afrique Résurrection 2026</p>
        </div>
        """
        params = {"from": SENDER_EMAIL, "to": [email], "subject": "🎬 Votre vidéo Afrique Résurrection est prête !", "html": html}
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {email}")
    except Exception as e:
        logger.error(f"Email error: {e}")


async def generate_video(project_id: str, image_paths: List[str], subtitles: List[str],
                         duration_per_image: float, enable_voiceover: bool = False,
                         voice_gender: str = "male", hd_quality: bool = False,
                         background_music: Optional[str] = None, transition_type: str = "zoomin",
                         ultra_fast_mode: bool = False, user_email: Optional[str] = None):
    try:
        # Check if cancelled
        if project_id in cancelled_projects:
            await update_project_status(project_id, status="cancelled", progress=0, progress_message="Génération annulée")
            cancelled_projects.discard(project_id)
            return
            
        await update_project_status(project_id, status="processing", progress=5, progress_message="Démarrage de la génération...")
        
        project_dir = UPLOAD_DIR / project_id
        output_dir = OUTPUT_DIR / project_id
        try:
            output_dir.mkdir(exist_ok=True, parents=True)
            test_file = output_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            logger.error(f"Directory creation or write permission error: {str(e)}")
            await update_project_status(project_id, status="error", error_message=f"Erreur de système de fichiers: {str(e)}")
            return
        
        total_images = len(image_paths)
        clip_paths = []
        audio_paths = []
        durations = []
        
        # Check cancellation
        if project_id in cancelled_projects:
            cancelled_projects.discard(project_id)
            await update_project_status(project_id, status="cancelled", progress=0, progress_message="Génération annulée")
            return
            
        # Generate voiceovers if enabled
        if enable_voiceover:
            await update_project_status(project_id, progress=8, progress_message="Génération des voix off...")
            for i, subtitle in enumerate(subtitles):
                # Check cancellation
                if project_id in cancelled_projects:
                    cancelled_projects.discard(project_id)
                    await update_project_status(project_id, status="cancelled", progress=0, progress_message="Génération annulée")
                    return
                    
                if subtitle and subtitle.strip():
                    audio_path = output_dir / f"voiceover_{i}.mp3"
                    success = await generate_voiceover(subtitle, audio_path, voice_gender)
                    if success:
                        audio_duration = await get_audio_duration(audio_path)
                        audio_paths.append(audio_path)
                        durations.append(max(audio_duration + 0.5, duration_per_image))
                    else:
                        audio_paths.append(None)
                        durations.append(duration_per_image)
                else:
                    audio_paths.append(None)
                    durations.append(duration_per_image)
        else:
            audio_paths = [None] * total_images
            durations = [duration_per_image] * total_images
        
        # Create individual clips with subtitles
        for i, (img_path, subtitle) in enumerate(zip(image_paths, subtitles)):
            # Check cancellation
            if project_id in cancelled_projects:
                cancelled_projects.discard(project_id)
                await update_project_status(project_id, status="cancelled", progress=0, progress_message="Génération annulée")
                return
                
            progress_val = 10 + int(((i + 1) / total_images) * 40)
            await update_project_status(project_id, status="processing", progress=progress_val, progress_message=f"Création du clip {i + 1}/{total_images}...")
            
            clip_duration = durations[i]
            clip_path = output_dir / f"clip_{i}.mp4"
            ass_path = output_dir / f"subtitle_{i}.ass"
            
            create_ass_subtitle(subtitle if subtitle else "", clip_duration, ass_path)
            
            # Mode Ultra Rapide: Ken Burns conservé mais optimisations maximales
            if ultra_fast_mode:
                video_filter = (
                    f"[0:v]scale=iw*max(1080/iw\\,1920/ih):ih*max(1080/iw\\,1920/ih):flags=bilinear,"
                    f"crop=1080:1920:x='if(gt(iw\\,1080)\\,(iw-1080)*t/{clip_duration}\\,0)':y='if(gt(ih\\,1920)\\,(ih-1920)/2\\,0)',"
                    f"format=yuv420p,ass={ass_path}[v]"
                )
                preset = "superfast"
                crf = "26"
            elif hd_quality:
                video_filter = (
                    f"[0:v]scale=iw*max(2160/iw\\,3840/ih):ih*max(2160/iw\\,3840/ih):flags=lanczos,"
                    f"crop=2160:3840:x='if(gt(iw\\,2160)\\,(iw-2160)*t/{clip_duration}\\,0)':y='if(gt(ih\\,3840)\\,(ih-3840)/2\\,0)',"
                    f"scale=1080:1920:flags=lanczos,"
                    f"unsharp=5:5:0.8:5:5:0.0,"
                    f"eq=contrast=1.03:brightness=0.01:saturation=1.05,"
                    f"format=yuv420p,ass={ass_path}[v]"
                )
                preset = "ultrafast"
                crf = "22"
            else:
                video_filter = (
                    f"[0:v]scale=iw*max(1080/iw\\,1920/ih):ih*max(1080/iw\\,1920/ih):flags=lanczos,"
                    f"crop=1080:1920:x='if(gt(iw\\,1080)\\,(iw-1080)*t/{clip_duration}\\,0)':y='if(gt(ih\\,1920)\\,(ih-1920)/2\\,0)',"
                    f"format=yuv420p,ass={ass_path}[v]"
                )
                preset = "ultrafast"
                crf = "24"
            
            if audio_paths[i] and audio_paths[i].exists():
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", img_path, "-i", str(audio_paths[i]),
                    "-filter_complex", f"{video_filter};[1:a]volume=2.0[a]",
                    "-map", "[v]", "-map", "[a]", "-t", str(clip_duration), "-r", "30",
                    "-c:v", "libx264", "-preset", preset, "-crf", crf,
                    "-profile:v", "high", "-level", "4.2",
                    "-threads", "0", "-g", "60", "-bf", "2",
                    "-b:v", "5M", "-maxrate", "6M", "-bufsize", "10M",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(clip_path)
                ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", img_path,
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-filter_complex", video_filter,
                    "-map", "[v]", "-map", "1:a", "-t", str(clip_duration), "-r", "30",
                    "-c:v", "libx264", "-preset", preset, "-crf", crf,
                    "-profile:v", "high", "-level", "4.2",
                    "-threads", "0", "-g", "60", "-bf", "2",
                    "-b:v", "5M", "-maxrate", "6M", "-bufsize", "10M",
                    "-c:a", "aac", "-b:a", "96k", "-shortest",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(clip_path)
                ]
            
            returncode, stdout, stderr = await run_ffmpeg(cmd)
            if returncode != 0:
                logger.error(f"FFmpeg error for clip {i + 1}: {stderr}")
                raise Exception(f"Erreur lors de la création du clip {i + 1}")
            
            if not clip_path.exists():
                raise Exception(f"Le clip {i + 1} n'a pas été créé correctement")
            
            clip_paths.append(clip_path)
        
        # Check cancellation before merge
        if project_id in cancelled_projects:
            cancelled_projects.discard(project_id)
            await update_project_status(project_id, status="cancelled", progress=0, progress_message="Génération annulée")
            return
            
        await update_project_status(project_id, progress=55, progress_message="Assemblage des clips...")
        
        merged_path = output_dir / "merged.mp4"
        
        # Mode Ultra Rapide: concat simple sans transitions
        if ultra_fast_mode:
            concat_file = output_dir / "concat.txt"
            with open(concat_file, 'w') as f:
                for clip_path in clip_paths:
                    f.write(f"file '{clip_path}'\n")
            
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-c", "copy", str(merged_path)
            ]
            returncode, stdout, stderr = await run_ffmpeg(cmd)
            if returncode != 0:
                logger.error(f"Error concatenating clips: {stderr}")
                raise Exception("Erreur lors de l'assemblage des clips")
        elif len(clip_paths) == 1:
            total_duration = durations[0]
            cmd = [
                "ffmpeg", "-y", "-i", str(clip_paths[0]),
                "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={total_duration-0.5}:d=0.5",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-profile:v", "high", "-level", "4.2",
                "-threads", "0",
                "-b:v", "4M", "-maxrate", "5M", "-bufsize", "8M",
                "-c:a", "copy",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(merged_path)
            ]
            returncode, stdout, stderr = await run_ffmpeg(cmd)
            if returncode != 0:
                logger.error(f"Error adding fades: {stderr}")
                shutil.copy(clip_paths[0], merged_path)
        else:
            fade_duration = 0.5
            input_args = []
            for clip_path in clip_paths:
                input_args.extend(["-i", str(clip_path)])
            
            filter_parts = []
            offset = 0
            current_label = "[0:v]"
            
            for i in range(len(clip_paths) - 1):
                next_label = f"[v{i}]" if i < len(clip_paths) - 2 else "[vout]"
                offset += durations[i] - fade_duration
                filter_parts.append(f"{current_label}[{i+1}:v]xfade=transition={transition_type}:duration={fade_duration}:offset={offset}{next_label}")
                current_label = next_label
            
            total_duration = sum(durations) - fade_duration * (len(clip_paths) - 1)
            video_filter = ";".join(filter_parts) + f";[vout]fade=t=in:st=0:d=0.5,fade=t=out:st={total_duration-0.5}:d=0.5[vfinal]"
            
            concat_file = output_dir / "concat.txt"
            with open(concat_file, 'w') as f:
                for clip_path in clip_paths:
                    f.write(f"file '{clip_path}'\n")
            
            temp_audio = output_dir / "temp_audio.aac"
            cmd_audio = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-vn", "-acodec", "aac", "-b:a", "128k", str(temp_audio)
            ]
            returncode_audio, _, stderr_audio = await run_ffmpeg(cmd_audio)
            if returncode_audio != 0 or not temp_audio.exists():
                logger.warning(f"Could not extract audio: {stderr_audio}")
            
            if transition_type in ["zoomin", "fade"] and temp_audio.exists():
                whoosh_source = ASSETS_DIR / "whoosh.mp3"
                if whoosh_source.exists() and len(clip_paths) > 1:
                    whoosh_inputs = []
                    for i in range(len(clip_paths) - 1):
                        whoosh_inputs.extend(["-i", str(whoosh_source)])
                    
                    # Réduire le volume du whoosh pour éviter conflit avec voix off
                    # et le décaler légèrement après le début de la transition
                    audio_filters = ["[0:a]volume=1.0[main]"]
                    for i in range(len(clip_paths) - 1):
                        # Décaler le whoosh de 0.15s après le début de la transition
                        # pour laisser la voix off finir proprement
                        whoosh_start = sum(durations[:i+1]) - fade_duration + 0.15
                        # Volume réduit à 0.8 pour ne pas couvrir la voix
                        audio_filters.append(f"[{i+1}:a]volume=0.8,adelay={int(whoosh_start*1000)}|{int(whoosh_start*1000)}[w{i}]")
                    
                    mix_inputs = "[main]" + "".join([f"[w{i}]" for i in range(len(clip_paths) - 1)])
                    filter_str = ";".join(audio_filters) + f";{mix_inputs}amix=inputs={len(clip_paths)}:duration=longest:normalize=0[aout]"
                    
                    final_audio = output_dir / "audio_with_whoosh.aac"
                    cmd_mix = [
                        "ffmpeg", "-y", "-i", str(temp_audio)
                    ] + whoosh_inputs + [
                        "-filter_complex", filter_str,
                        "-map", "[aout]", "-c:a", "aac", "-b:a", "128k", str(final_audio)
                    ]
                    
                    returncode, stdout, stderr = await run_ffmpeg(cmd_mix)
                    if returncode == 0 and final_audio.exists():
                        temp_audio = final_audio
                    else:
                        logger.warning(f"Could not add whoosh effects: {stderr}")
            
            if temp_audio.exists():
                cmd = [
                    "ffmpeg", "-y"
                ] + input_args + [
                    "-i", str(temp_audio),
                    "-filter_complex", video_filter,
                    "-map", "[vfinal]", "-map", f"{len(clip_paths)}:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-profile:v", "high", "-level", "4.2",
                    "-threads", "0",
                    "-b:v", "4M", "-maxrate", "5M", "-bufsize", "8M",
                    "-c:a", "aac", "-b:a", "96k",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(merged_path)
                ]
            else:
                cmd = [
                    "ffmpeg", "-y"
                ] + input_args + [
                    "-filter_complex", video_filter,
                    "-map", "[vfinal]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-profile:v", "high", "-level", "4.2",
                    "-threads", "0",
                    "-b:v", "4M", "-maxrate", "5M", "-bufsize", "8M",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(merged_path)
                ]
            
            returncode, stdout, stderr = await run_ffmpeg(cmd)
            if returncode != 0:
                logger.error(f"Error with xfade: {stderr}")
                cmd_fallback = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                    "-c", "copy", str(merged_path)
                ]
                await run_ffmpeg(cmd_fallback)
            
            if temp_audio.exists():
                temp_audio.unlink()
        
        # Check cancellation before adding logo
        if project_id in cancelled_projects:
            cancelled_projects.discard(project_id)
            await update_project_status(project_id, status="cancelled", progress=0, progress_message="Génération annulée")
            return
            
        await update_project_status(project_id, progress=75, progress_message="Ajout du logo...")
        
        if not merged_path.exists():
            logger.error(f"merged.mp4 not found at {merged_path}")
            raise Exception("La vidéo assemblée n'a pas été créée correctement")
        
        logo_path = ASSETS_DIR / "logo.png"
        final_video_path = OUTPUT_DIR / f"{project_id}_final.mp4"
        
        # Mode Ultra Rapide: juste logo, pas de musique
        if ultra_fast_mode and logo_path.exists():
            video_filter = "[1:v]scale=750:-1[logo];[0:v][logo]overlay=550:-45"
            cmd = [
                "ffmpeg", "-y", "-i", str(merged_path), "-i", str(logo_path), "-filter_complex",
                f"{video_filter}",
                "-c:v", "libx264", "-preset", "superfast", "-crf", "26",
                "-profile:v", "high", "-level", "4.2",
                "-threads", "0",
                "-c:a", "copy", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final_video_path)
            ]
            returncode, stdout, stderr = await run_ffmpeg(cmd)
            if returncode != 0:
                logger.error(f"Error adding logo: {stderr}")
                shutil.copy(merged_path, final_video_path)
        elif logo_path.exists():
            video_filter = "[1:v]scale=750:-1[logo];[0:v][logo]overlay=550:-45"
            
            if background_music:
                await update_project_status(project_id, progress=80, progress_message="Ajout de la musique de fond...")
                music_file = ASSETS_DIR / f"{background_music}.mp3"
                
                if music_file.exists():
                    video_duration = sum(durations)
                    fadeout_start = max(0, video_duration - 3)
                    
                    cmd = [
                        "ffmpeg", "-y", "-i", str(merged_path), "-i", str(logo_path), "-i", str(music_file),
                        "-filter_complex",
                        f"{video_filter}[v];"
                        f"[2:a]volume=0.50,afade=t=out:st={fadeout_start}:d=3[music];"
                        f"[0:a][music]amix=inputs=2:duration=shortest:weights=1 0.50[a]",
                        "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-profile:v", "high", "-level", "4.2",
                        "-threads", "0",
                        "-b:v", "4M", "-maxrate", "5M", "-bufsize", "8M",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(final_video_path)
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y", "-i", str(merged_path), "-i", str(logo_path), "-filter_complex",
                        f"{video_filter}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-profile:v", "high", "-level", "4.2",
                        "-threads", "0",
                        "-b:v", "4M", "-maxrate", "5M", "-bufsize", "8M",
                        "-c:a", "copy", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final_video_path)
                    ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-i", str(merged_path), "-i", str(logo_path), "-filter_complex",
                    f"{video_filter}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-profile:v", "high", "-level", "4.2",
                    "-threads", "0",
                    "-b:v", "4M", "-maxrate", "5M", "-bufsize", "8M",
                    "-c:a", "copy", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final_video_path)
                ]
            
            returncode, stdout, stderr = await run_ffmpeg(cmd)
            if returncode != 0:
                logger.error(f"Error adding logo/music: {stderr}")
                shutil.copy(merged_path, final_video_path)
        else:
            shutil.copy(merged_path, final_video_path)
        
        await update_project_status(project_id, status="completed", progress=100, progress_message="Vidéo terminée !", video_url=f"/api/download/{project_id}")
        
        # Send email with download link if email provided
        if user_email:
            base_url = os.environ.get('REACT_APP_BACKEND_URL', 'https://auto-reels-14.preview.emergentagent.com')
            download_url = f"{base_url}/api/download/{project_id}"
            await send_download_email(user_email, project_id, download_url)
        
        # Cleanup
        for clip_path in clip_paths:
            if clip_path.exists() and clip_path != final_video_path:
                clip_path.unlink()
        for f in output_dir.glob("merged*.mp4"):
            if f != final_video_path:
                f.unlink()
        for f in output_dir.glob("subtitle_*.ass"):
            f.unlink()
        for f in output_dir.glob("voiceover_*.mp3"):
            f.unlink()
        for f in output_dir.glob("audio_*.aac"):
            f.unlink()
        concat_file = output_dir / "concat.txt"
        if concat_file.exists():
            concat_file.unlink()
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error generating video for project {project_id}: {error_msg}")
        logger.error(f"Error type: {type(e).__name__}")
        await update_project_status(
            project_id,
            status="error",
            error_message=f"Erreur de génération: {error_msg[:200]}"
        )


@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Afrique Résurrection Video Generator HD"}


@api_router.post("/create-video", response_model=VideoProjectResponse)
async def create_video(
    background_tasks: BackgroundTasks,
    images: List[UploadFile] = File(default=[]),
    subtitles: str = Form(default="[]"),
    duration_per_image: float = Form(default=5.0),
    enable_voiceover: bool = Form(default=False),
    voice_gender: str = Form(default="male"),
    hd_quality: bool = Form(default=False),
    background_music: Optional[str] = Form(default=None),
    transition_type: str = Form(default="zoomin"),
    ultra_fast_mode: bool = Form(default=False),
    user_email: Optional[str] = Form(default=None)
):
    try:
        subtitles_list = json.loads(subtitles)
        if not images or len(images) == 0:
            raise HTTPException(status_code=400, detail="No images provided")
        if len(images) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 images allowed")
        while len(subtitles_list) < len(images):
            subtitles_list.append("")
        
        project_id = str(uuid.uuid4())
        project_dir = UPLOAD_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        
        image_paths = []
        for i, image in enumerate(images):
            if not image.content_type or not image.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail=f"File {image.filename} is not an image")
            file_ext = Path(image.filename).suffix or ".jpg"
            file_path = project_dir / f"image_{i}{file_ext}"
            async with aiofiles.open(file_path, 'wb') as f:
                content = await image.read()
                await f.write(content)
            image_paths.append(str(file_path))
        
        project = VideoProject(
            id=project_id,
            status="pending",
            progress=0,
            progress_message="En attente...",
            image_paths=image_paths,
            subtitles=subtitles_list[:len(images)],
            duration_per_image=duration_per_image,
            total_images=len(images),
            enable_voiceover=enable_voiceover if not ultra_fast_mode else False,
            voice_gender=voice_gender,
            hd_quality=hd_quality if not ultra_fast_mode else False,
            background_music=background_music if not ultra_fast_mode else None,
            transition_type=transition_type,
            user_email=user_email
        )
        await db.video_projects.insert_one(project.model_dump())
        
        background_tasks.add_task(
            generate_video,
            project_id,
            image_paths,
            subtitles_list[:len(images)],
            duration_per_image,
            False if ultra_fast_mode else enable_voiceover,
            voice_gender,
            False if ultra_fast_mode else hd_quality,
            None if ultra_fast_mode else background_music,
            transition_type,
            ultra_fast_mode,
            user_email
        )
        
        return VideoProjectResponse(
            project_id=project_id,
            status="processing",
            message="Video generation started",
            total_images=len(images)
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid subtitles format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/project/{project_id}", response_model=ProjectStatus)
async def get_project_status(project_id: str):
    project = await db.video_projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectStatus(
        id=project["id"],
        status=project["status"],
        progress=project["progress"],
        progress_message=project["progress_message"],
        video_url=project.get("video_url"),
        error_message=project.get("error_message")
    )


@api_router.delete("/project/{project_id}")
async def cancel_video_generation(project_id: str):
    """Cancel ongoing video generation"""
    project = await db.video_projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["status"] == "processing":
        cancelled_projects.add(project_id)
        await update_project_status(project_id, status="cancelled", progress=0, progress_message="Annulation en cours...")
        return {"status": "success", "message": "Cancellation requested"}
    else:
        return {"status": "info", "message": f"Project is {project['status']}, cannot cancel"}


@api_router.get("/download/{project_id}")
async def download_video(project_id: str):
    project = await db.video_projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video not ready yet")
    video_path = OUTPUT_DIR / f"{project_id}_final.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"afrique_resurrection_hd_{project_id[:8]}.mp4"
    )


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
