import os
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from moviepy.video.fx.all import crop
import subprocess
# from .utils import convert_time_to_seconds # No longer needed for extract_video_segments directly
from .utils import format_time # May be useful for logging or consistent naming if desired

def convert_video_aspect_ratio(input_file_path: str, output_file_path: str, target_aspect_ratio_str: str) -> str | None:
    """
    Converts a video to a target aspect ratio by cropping and centering.

    Args:
        input_file_path (str): Path to the input video file.
        output_file_path (str): Path to save the processed video.
        target_aspect_ratio_str (str): Target aspect ratio as a string (e.g., '9:16', '1:1').

    Returns:
        str | None: The output_file_path if successful, else None.
    """
    try:
        ar_w_str, ar_h_str = target_aspect_ratio_str.split(':')
        ar_w = int(ar_w_str)
        ar_h = int(ar_h_str)
        if ar_w <= 0 or ar_h <= 0:
            raise ValueError("Aspect ratio parts must be positive.")
        target_ar = ar_w / ar_h
    except ValueError as e:
        print(f"Error: Invalid target_aspect_ratio_str '{target_aspect_ratio_str}'. Expected format like '9:16'. Details: {e}")
        return None

    if not os.path.exists(input_file_path):
        print(f"Error: Input file not found at {input_file_path}")
        return None

    clip = None
    cropped_clip = None
    try:
        clip = VideoFileClip(input_file_path)
        orig_w, orig_h = clip.size

        current_ar = orig_w / orig_h

        if current_ar > target_ar:  # Video is wider than target (e.g., 16:9 source to 9:16 target)
            new_height = orig_h
            new_width = int(orig_h * target_ar)
        else:  # Video is taller than target or same AR (e.g., 16:9 source to 1:1 target, or 9:16 to 9:16)
            new_width = orig_w
            new_height = int(orig_w / target_ar)

        # Ensure new dimensions are not zero if original dimensions were tiny or target AR extreme
        if new_width == 0 or new_height == 0:
            print(f"Error: Calculated new dimensions are zero (w:{new_width}, h:{new_height}). Original: {orig_w}x{orig_h}, Target AR: {target_ar_str}")
            return None

        cropped_clip = clip.fx(crop, width=new_width, height=new_height, x_center=orig_w / 2, y_center=orig_h / 2)

        output_dir = os.path.dirname(output_file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        temp_audio_dir = os.path.dirname(output_file_path) if os.path.dirname(output_file_path) else '.'
        cropped_clip.write_videofile(
            output_file_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile_path=temp_audio_dir,
            logger=None # supresses default progress bar, use 'bar' for progress bar
        )
        print(f"Converted '{input_file_path}' to aspect ratio {target_aspect_ratio_str}, saved as '{output_file_path}'")
        return output_file_path
    except Exception as e:
        print(f"Error during video aspect ratio conversion for '{input_file_path}': {e}")
        return None
    finally:
        if cropped_clip:
            cropped_clip.close()
        if clip:
            clip.close()

def extract_video_segments(video_file_path: str, start_seconds: float, end_seconds: float, output_file_path: str) -> bool:
    """
    Extracts a segment from the video_file_path using ffmpeg from start_seconds to end_seconds,
    saving it to output_file_path.
    Returns True on success, False on failure.
    """
    if not os.path.exists(video_file_path):
        print(f"Error: Input video file not found: {video_file_path}")
        return False

    output_dir = os.path.dirname(output_file_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    duration = end_seconds - start_seconds
    if duration <= 0:
        print(f"Error: Segment duration is not positive (start: {start_seconds}, end: {end_seconds}). Skipping extraction.")
        return False

    # ffmpeg command using seconds for -ss (start) and -t (duration) or -to (end time)
    # Using -to is generally safer with -ss if input -ss is not perfectly accurate for keyframes.
    # However, -t (duration) is also common. Let's use -to for now.
    command = [
        'ffmpeg',
        '-i', video_file_path,
        '-ss', str(start_seconds),
        '-to', str(end_seconds),
        '-c', 'copy', # Copy codecs to avoid re-encoding, much faster
        '-y', # Overwrite output file if it exists
        output_file_path
    ]

    command_str = " ".join(f'"{c}"' if " " in c else c for c in command) # For printing
    print(f"Executing segment extraction command: {command_str}")

    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Successfully extracted segment from {start_seconds:.2f}s to {end_seconds:.2f}s, saved as {output_file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing ffmpeg for segment extraction: {e}")
        print(f"ffmpeg stdout: {e.stdout}")
        print(f"ffmpeg stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during segment extraction: {e}")
        return False


def add_captions_to_video(
    video_path: str,
    transcription_segments: list,
    output_path: str,
    fontsize: int = 24,
    font: str = 'Arial-Bold',
    color: str = 'white',
    bg_color: str = 'black',
    stroke_color: str = 'black',
    stroke_width: float = 0.5,
    position: tuple = ('center', 0.85)
):
    """
    Adds captions to a video based on transcription segments.

    Args:
        video_path (str): Path to the input video file.
        transcription_segments (list): List of dicts, e.g., [{'text': "Hello", 'start': 0.5, 'end': 2.0}, ...].
        output_path (str): Path to save the video with captions.
        fontsize (int): Font size for the captions.
        font (str): Font type for the captions.
        color (str): Text color for the captions.
        bg_color (str): Background color for the text. Use 'transparent' for no background.
        stroke_color (str): Color of the text border.
        stroke_width (float): Width of the text border.
        position (tuple): Position of the text (MoviePy format).
    """
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return

    video_clip = VideoFileClip(video_path)

    caption_clips = []
    for segment in transcription_segments:
        text = segment.get('text', '').strip()
        start_time = segment.get('start')
        end_time = segment.get('end')

        if not (text and start_time is not None and end_time is not None):
            continue

        duration = end_time - start_time
        if duration <= 0:
            continue

        text_width = video_clip.w * 0.9

        current_bg_color = 'none' if bg_color == 'transparent' else bg_color

        txt_clip = TextClip(
            text,
            fontsize=fontsize,
            font=font,
            color=color,
            bg_color=current_bg_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            method='caption',
            align='center',
            size=(text_width, None)
        )

        txt_clip = txt_clip.set_position(position).set_duration(duration).set_start(start_time)
        caption_clips.append(txt_clip)

    if not caption_clips:
        print("No valid caption segments found to add. Original video will not be modified.")
        video_clip.close()
        return

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    final_clip = CompositeVideoClip([video_clip] + caption_clips, size=video_clip.size)

    temp_audio_dir = os.path.dirname(output_path) if os.path.dirname(output_path) else '.'

    try:
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile_path=temp_audio_dir
        )
        print(f"Video with captions saved to {output_path}")
    except Exception as e:
        print(f"Error writing video file: {e}")
    finally:
        video_clip.close()
        final_clip.close()
        for tc in caption_clips:
            tc.close()
