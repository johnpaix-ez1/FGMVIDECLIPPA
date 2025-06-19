# tests/test_core/test_utils.py
import pytest
from clipify.core import utils
import os
from unittest.mock import patch, MagicMock

def test_format_time():
    assert utils.format_time(65) == "1:05"
    assert utils.format_time(3600) == "60:00" # Assuming current logic (MM:SS)
    assert utils.format_time(3665) == "61:05" # MM:SS
    assert utils.format_time(0) == "0:00"
    # Test case for hours, if format_time is updated to handle HH:MM:SS
    # assert utils.format_time(3661) == "1:01:01" # If HH:MM:SS format is supported

def test_convert_time_to_seconds():
    assert utils.convert_time_to_seconds("1:05") == 65
    assert utils.convert_time_to_seconds("0:30") == 30
    assert utils.convert_time_to_seconds("1:00:00") == 3600
    with pytest.raises(ValueError):
        utils.convert_time_to_seconds("invalid")
    with pytest.raises(ValueError):
        utils.convert_time_to_seconds("1:2:3:4")


@patch('clipify.core.utils.yt_dlp.YoutubeDL')
def test_download_youtube_video_success(mock_youtube_dl, tmp_path):
    # Create a realistic, though simplified, info_dict that yt-dlp might return
    # after a successful download, specifically the 'requested_downloads' part.
    fake_title = "test_video_title"
    fake_ext = "mp4"
    # Use tmp_path to ensure paths are valid in the test environment
    expected_filename = os.path.join(tmp_path, f"{fake_title}.{fake_ext}")

    info_dict_after_download = {
        'title': fake_title,
        'ext': fake_ext,
        'requested_downloads': [
            {
                'filepath': expected_filename,
                # ... other keys like 'filesize', 'duration_string', etc.
            }
        ]
        # ... other top-level keys like 'duration', 'channel', etc.
    }

    mock_ydl_instance = MagicMock()
    # extract_info is called with download=True, so it performs the download
    # and its return value (info_dict) should contain info about the downloaded file.
    mock_ydl_instance.extract_info.return_value = info_dict_after_download

    # prepare_filename is usually for getting filename before download, or if outtmpl is a simple path.
    # With outtmpl as a template and download=True, the actual filename comes from extract_info's result.
    # We can mock it to return what would be expected if it were used to confirm.
    mock_ydl_instance.prepare_filename.return_value = expected_filename

    mock_youtube_dl.return_value.__enter__.return_value = mock_ydl_instance

    video_url = 'https://www.youtube.com/watch?v=test'

    # Simulate that the file was actually created by the mock download
    # In a real scenario, yt-dlp would create this file.
    # For the mock, we ensure our logic correctly extracts the path from info_dict.
    # No need to actually create the file for this unit test if we trust yt-dlp part
    # and only test our path extraction logic from its output.
    # However, the function itself has an os.path.exists check in some error paths,
    # so it might be safer to simulate its existence if those paths are tested.
    # For the success path tested here, it's primarily about getting the path string.

    downloaded_path = utils.download_youtube_video(video_url, output_path=str(tmp_path))

    assert downloaded_path == expected_filename
    mock_youtube_dl.assert_called_once() # Check that YoutubeDL was initialized
    # Check extract_info was called correctly
    mock_ydl_instance.extract_info.assert_called_once_with(video_url, download=True)


@patch('clipify.core.utils.yt_dlp.YoutubeDL')
def test_download_youtube_video_download_error(mock_youtube_dl, tmp_path):
    mock_ydl_instance = MagicMock()
    # Simulate a download error during extract_info
    mock_ydl_instance.extract_info.side_effect = utils.yt_dlp.utils.DownloadError("Simulated download error")
    mock_youtube_dl.return_value.__enter__.return_value = mock_ydl_instance

    video_url = 'https://www.youtube.com/watch?v=testerror'
    downloaded_path = utils.download_youtube_video(video_url, output_path=str(tmp_path))

    assert downloaded_path is None # Expect None on download failure
    mock_youtube_dl.assert_called_once()
    mock_ydl_instance.extract_info.assert_called_once_with(video_url, download=True)

@patch('clipify.core.utils.yt_dlp.YoutubeDL')
def test_download_youtube_video_no_filepath_in_info(mock_youtube_dl, tmp_path):
    mock_ydl_instance = MagicMock()
    # Simulate info_dict missing 'requested_downloads' or 'filepath'
    mock_ydl_instance.extract_info.return_value = {'title': 'test', 'ext': 'mp4'} # Missing file path info
    mock_youtube_dl.return_value.__enter__.return_value = mock_ydl_instance

    video_url = 'https://www.youtube.com/watch?v=testmissingpath'
    downloaded_path = utils.download_youtube_video(video_url, output_path=str(tmp_path))

    assert downloaded_path is None # Expect None if path cannot be determined
    mock_youtube_dl.assert_called_once()
    mock_ydl_instance.extract_info.assert_called_once_with(video_url, download=True)
