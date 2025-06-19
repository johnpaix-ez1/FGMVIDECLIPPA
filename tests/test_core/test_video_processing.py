# tests/test_core/test_video_processing.py
import pytest
from clipify.core import video_processing
from unittest.mock import patch, MagicMock, call
import os

@patch('subprocess.run')
def test_extract_video_segments_success(mock_subprocess_run, tmp_path):
    # Simulate a successful subprocess run for ffmpeg
    mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="ffmpeg output", stderr="")

    video_file = tmp_path / "dummy_video.mp4"
    video_file.touch() # Create a dummy file for os.path.exists checks
    output_file = tmp_path / "segment.mp4"
    start_time, end_time = 10.0, 20.0

    # The function now returns True on success, False on failure
    success = video_processing.extract_video_segments(str(video_file), start_time, end_time, str(output_file))

    assert success is True # Check for True on success

    # Check that subprocess.run was called
    mock_subprocess_run.assert_called_once()
    args, kwargs = mock_subprocess_run.call_args

    # args[0] is the command list
    command_list = args[0]
    assert command_list[0] == 'ffmpeg'
    assert str(video_file) in command_list
    assert str(output_file) in command_list
    assert '-ss' in command_list
    assert str(start_time) in command_list
    assert '-to' in command_list
    assert str(end_time) in command_list
    assert kwargs.get('check') is True # Ensure it raises an error on non-zero exit

@patch('subprocess.run')
def test_extract_video_segments_failure(mock_subprocess_run, tmp_path):
    # Simulate a failed subprocess run for ffmpeg
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="ffmpeg", stderr="ffmpeg error")

    video_file = tmp_path / "dummy_video.mp4"
    video_file.touch()
    output_file = tmp_path / "segment_fail.mp4"
    start_time, end_time = 10.0, 20.0

    success = video_processing.extract_video_segments(str(video_file), start_time, end_time, str(output_file))

    assert success is False # Check for False on failure
    mock_subprocess_run.assert_called_once()


@patch('clipify.core.video_processing.VideoFileClip')
def test_convert_video_aspect_ratio_landscape_to_portrait(mock_vfc, tmp_path):
    mock_clip_instance = MagicMock()
    mock_clip_instance.size = (1920, 1080) # Original landscape
    mock_clip_instance.w = 1920
    mock_clip_instance.h = 1080
    # mock_clip_instance.duration = 10.0 # Not strictly needed for this test by current func

    mock_cropped_clip = MagicMock()
    # Simulate the chain: clip.fx(...)(crop_params)
    # The crop function itself is usually from moviepy.video.fx.all.crop
    # So, if fx is a method that takes (crop_func, **kwargs), then mock_clip_instance.fx.return_value is not needed.
    # Instead, the crop function is passed to fx.
    # For this test, let's assume fx applies the crop and returns the new clip.
    mock_clip_instance.fx.return_value = mock_cropped_clip

    mock_vfc.return_value.__enter__.return_value = mock_clip_instance # If VideoFileClip is used in a context manager
    mock_vfc.return_value = mock_clip_instance # If used directly

    input_file = str(tmp_path / "input.mp4")
    # Create a dummy file for os.path.exists checks within the function
    with open(input_file, 'w') as f: f.write('dummy video data')
    output_file = str(tmp_path / "output_9_16.mp4")

    result_path = video_processing.convert_video_aspect_ratio(input_file, output_file, '9:16')

    assert result_path == output_file
    mock_vfc.assert_called_once_with(input_file)

    # Expected: new_width = 1080 * (9/16) = 607.5 -> int(607.5) = 607. new_height = 1080.
    # Check that clip.fx was called with crop
    # The first argument to fx should be the crop function, and then kwargs for crop
    # This part of mocking is tricky. Let's assume fx is called with crop parameters directly as kwargs for simplicity.
    # A more accurate mock would involve `from moviepy.video.fx.all import crop` and `mock_clip_instance.fx.assert_called_with(crop, width=..., ...)`

    # Given the structure `cropped_clip = clip.fx(crop, width=new_width, ...)`
    # We check the call to `fx`
    actual_call = mock_clip_instance.fx.call_args
    assert actual_call is not None, "fx method was not called"
    # First positional arg to fx is the effect (crop function itself, hard to assert by name without importing it here)
    # We can check the kwargs passed to fx, which are the parameters for crop
    assert actual_call.kwargs['width'] == 607 # int(1080 * 9/16)
    assert actual_call.kwargs['height'] == 1080
    assert actual_call.kwargs['x_center'] == 1920 / 2
    assert actual_call.kwargs['y_center'] == 1080 / 2

    mock_cropped_clip.write_videofile.assert_called_once_with(output_file, codec='libx264', audio_codec='aac', temp_audiofile_path=str(tmp_path), logger=None)

    # Ensure clips are closed
    # If VideoFileClip is used as a context manager, close is handled.
    # If not, direct calls to close() should be asserted.
    # The refactored code uses try/finally to close clips.
    mock_clip_instance.close.assert_called_once()
    mock_cropped_clip.close.assert_called_once()


@patch('clipify.core.video_processing.VideoFileClip')
@patch('clipify.core.video_processing.TextClip')
@patch('clipify.core.video_processing.CompositeVideoClip')
def test_add_captions_to_video_success(mock_composite_clip, mock_text_clip, mock_vfc, tmp_path):
    mock_video_clip_instance = MagicMock(w=1280, h=720, size=(1280,720), duration=10.0)
    # If VideoFileClip is used in a context manager style by the SUT:
    # mock_vfc.return_value.__enter__.return_value = mock_video_clip_instance
    # If it's used directly:
    mock_vfc.return_value = mock_video_clip_instance

    mock_final_composite_clip = MagicMock()
    mock_composite_clip.return_value = mock_final_composite_clip

    # Each call to TextClip returns a new mock TextClip instance
    # To check calls on each, use a list of mocks or side_effect
    mock_text_instances = [MagicMock(), MagicMock()]
    mock_text_clip.side_effect = mock_text_instances

    video_path = str(tmp_path / "input.mp4")
    open(video_path, 'w').write('dummy') # Make file exist for os.path.exists
    output_path = str(tmp_path / "captioned_video.mp4")
    segments = [{'text': 'Hello', 'start': 1.0, 'end': 3.0}, {'text': 'World', 'start': 4.0, 'end': 6.0}]

    video_processing.add_captions_to_video(video_path, segments, output_path)

    mock_vfc.assert_called_once_with(video_path)
    assert mock_text_clip.call_count == 2

    # Check call for "Hello"
    mock_text_clip.assert_any_call('Hello', fontsize=24, font='Arial-Bold', color='white', bg_color='black', stroke_color='black', stroke_width=0.5, method='caption', align='center', size=(mock_video_clip_instance.w * 0.9, None))
    # Check call for "World"
    mock_text_clip.assert_any_call('World', fontsize=24, font='Arial-Bold', color='white', bg_color='black', stroke_color='black', stroke_width=0.5, method='caption', align='center', size=(mock_video_clip_instance.w * 0.9, None))

    for instance in mock_text_instances:
        instance.set_position.assert_called()
        instance.set_duration.assert_called()
        instance.set_start.assert_called()
        instance.close.assert_called_once() # Check that individual text clips are closed

    # Check that CompositeVideoClip was called with the main video clip and all created text clips
    mock_composite_clip.assert_called_once_with([mock_video_clip_instance] + mock_text_instances, size=mock_video_clip_instance.size)

    # Check that write_videofile was called on the final composite clip
    mock_final_composite_clip.write_videofile.assert_called_once_with(output_path, codec='libx264', audio_codec='aac', temp_audiofile_path=str(tmp_path))

    # Check that all main clips are closed
    mock_video_clip_instance.close.assert_called_once()
    mock_final_composite_clip.close.assert_called_once()
