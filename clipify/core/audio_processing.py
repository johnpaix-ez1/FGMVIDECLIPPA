import os
import subprocess
import whisper

def extract_audio_from_video(video_file_path: str, output_audio_path: str) -> str:
    """
    Extracts audio from a video file and saves it to the specified output_audio_path.
    Returns the output_audio_path on success, None on failure.
    """

    output_dir = os.path.dirname(output_audio_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Properly escape file paths for the ffmpeg command
    escaped_video_file = video_file_path.replace('"', '\\"')
    escaped_audio_file = output_audio_path.replace('"', '\\"')

    # Ensure the output is a .wav file as Whisper typically expects that
    if not output_audio_path.lower().endswith(".wav"):
        print(f"Warning: Output audio path '{output_audio_path}' is not a .wav file. Forcing .wav for compatibility.")
        # You might want to raise an error or adjust the path more robustly
        output_audio_path = os.path.splitext(output_audio_path)[0] + ".wav"
        escaped_audio_file = output_audio_path.replace('"', '\\"')

    command = f'ffmpeg -i "{escaped_video_file}" -ab 160k -ac 2 -ar 44100 -vn "{escaped_audio_file}" -y'

    print(f"Executing audio extraction command: {command}")
    try:
        process = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"Audio extracted successfully: {output_audio_path}")
        return output_audio_path
    except subprocess.CalledProcessError as e:
        print(f"Error executing ffmpeg command for audio extraction: {e}")
        print(f"ffmpeg stdout: {e.stdout}")
        print(f"ffmpeg stderr: {e.stderr}")
        return None

def transcribe_audio_with_whisper(audio_file):
    """Transcribes an audio file using Whisper."""
    if not os.path.exists(audio_file):
        print(f"Audio file not found: {audio_file}")
        return None
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_file, word_timestamps=True)
        return result
    except Exception as e:
        print(f"Error during transcription: {e}")
        return None
