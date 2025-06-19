import os
import yt_dlp

# Note: nltk.tokenize.sent_tokenize was moved to content_analysis.py

def download_youtube_video(url, output_path='Test Videos'):
    """Downloads a YouTube video."""
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True) # download=True is important
            if not info_dict: # download=False would require checking info_dict here
                print(f"yt-dlp failed to extract info for URL: {url}")
                return None
            # prepare_filename is typically used with download=False, but with download=True,
            # it can confirm the file path based on the template.
            # If download=True, ydl.extract_info itself should return the filename in info_dict.
            # Let's ensure we get the filename correctly after download.
            # The 'requested_downloads' key usually holds info about downloaded files.
            if 'requested_downloads' in info_dict and info_dict['requested_downloads']:
                 # Get the filepath of the first downloaded file
                video_file = info_dict['requested_downloads'][0]['filepath']
            elif 'filename' in info_dict: # Fallback for some cases
                video_file = info_dict['filename']
            elif 'title' in info_dict and 'ext' in info_dict : # Construct if absolutely necessary (less reliable)
                 video_file = ydl.prepare_filename(info_dict) #This might be based on template before download
                 # ensure it exists if constructed this way
                 if not os.path.exists(video_file):
                    print(f"Downloaded video file not found at constructed path: {video_file}")
                    # Search for it in output_path as a last resort
                    generated_title_part = info_dict['title'] # A simplified search
                    possible_files = [f for f in os.listdir(output_path) if generated_title_part in f]
                    if possible_files:
                        video_file = os.path.join(output_path, possible_files[0])
                        print(f"Found video file: {video_file}")
                    else:
                        print(f"Still couldn't locate downloaded file for {info_dict['title']}")
                        return None

            else: # If filename cannot be determined
                print(f"Could not determine the filename of the downloaded video for URL: {url}")
                return None

        if not os.path.exists(video_file):
            print(f"Downloaded video file does not exist: {video_file}")
            # This case might indicate an issue with yt-dlp's output or our path determination.
            # Try to get it directly from ydl.prepare_filename as a last resort if download was true.
            # This is usually how it's done if ydl_opts['outtmpl'] is a simple path not a template string.
            # However, with a template, info_dict should be primary.
            check_path = ydl.prepare_filename(info_dict) # Re-check with template
            if os.path.exists(check_path):
                video_file = check_path
            else:
                 print(f"Final check for video file at {check_path} also failed.")
                 return None

        print(f"Video downloaded successfully: {video_file}")
        return video_file
    except yt_dlp.utils.DownloadError as e:
        print(f"Error downloading video from {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during YouTube download: {e}")
        return None

def format_time(seconds):
    """Formats time in seconds to MM:SS or HH:MM:SS string."""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    hours = int(minutes // 60)
    minutes = int(minutes % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def convert_time_to_seconds(time_str):
    """
    Converts a time string in the format HH:MM:SS or MM:SS to seconds.
    Handles cases where the time string may not include hours.
    """
    parts = time_str.split(':')
    if len(parts) == 3:  # Includes hours
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:  # Excludes hours
        m, s = map(int, parts)
        return m * 60 + s
    else:
        raise ValueError("Invalid time format. Expected HH:MM:SS or MM:SS.")
