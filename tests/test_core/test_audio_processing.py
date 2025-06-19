# tests/test_core/test_audio_processing.py
import pytest
from clipify.core import audio_processing
import os
import subprocess # Import for CalledProcessError
from unittest.mock import patch, MagicMock

@patch('subprocess.run')
def test_extract_audio_from_video_success(mock_subprocess_run, tmp_path):
    # Simulate a successful subprocess run
    mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="ffmpeg output", stderr="")

    video_file = tmp_path / "dummy_video.mp4"
    video_file.touch()
    output_audio_path = tmp_path / "audio.wav" # Explicitly .wav

    result_path = audio_processing.extract_audio_from_video(str(video_file), str(output_audio_path))

    assert result_path == str(output_audio_path)

    # Check that subprocess.run was called
    mock_subprocess_run.assert_called_once()
    args, kwargs = mock_subprocess_run.call_args

    # Basic check of the command structure
    command_list = args[0] # args[0] is the command list/string based on shell=True/False
    assert 'ffmpeg' in command_list
    assert f'"{str(video_file)}"' in command_list # Check for quoted video file
    assert f'"{str(output_audio_path)}"' in command_list # Check for quoted audio file
    assert "-y" in command_list # Check for overwrite flag
    assert kwargs.get('shell') == True
    assert kwargs.get('check') == True


@patch('subprocess.run')
def test_extract_audio_from_video_ffmpeg_error(mock_subprocess_run, tmp_path):
    # Simulate an ffmpeg error by raising CalledProcessError
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="ffmpeg ...", output="ffmpeg output", stderr="ffmpeg error"
    )

    video_file = tmp_path / "error_video.mp4"
    video_file.touch()
    output_audio_path = tmp_path / "audio_error.wav"

    result_path = audio_processing.extract_audio_from_video(str(video_file), str(output_audio_path))

    assert result_path is None # Expect None on failure
    mock_subprocess_run.assert_called_once()

@patch('subprocess.run')
def test_extract_audio_from_video_forces_wav(mock_subprocess_run, tmp_path):
    mock_subprocess_run.return_value = MagicMock(returncode=0)
    video_file = tmp_path / "video.mp4"
    video_file.touch()
    output_audio_non_wav = tmp_path / "audio.mp3" # Input as mp3
    expected_output_audio_wav = tmp_path / "audio.wav" # Expected output as wav

    result_path = audio_processing.extract_audio_from_video(str(video_file), str(output_audio_non_wav))

    assert result_path == str(expected_output_audio_wav) # Should return .wav path
    args, kwargs = mock_subprocess_run.call_args
    command_list = args[0]
    assert f'"{str(expected_output_audio_wav)}"' in command_list # Command should use .wav

@patch('clipify.core.audio_processing.whisper.load_model')
def test_transcribe_audio_with_whisper_success(mock_load_model, tmp_path):
    mock_model_instance = MagicMock()
    mock_transcription = {'text': 'Hello world', 'segments': []}
    mock_model_instance.transcribe.return_value = mock_transcription
    mock_load_model.return_value = mock_model_instance

    audio_file = tmp_path / "dummy_audio.wav"
    # It's good practice for mock tests that the file exists if the function checks for it
    audio_file.touch()

    result = audio_processing.transcribe_audio_with_whisper(str(audio_file))

    assert result == mock_transcription
    mock_load_model.assert_called_once_with("base")
    mock_model_instance.transcribe.assert_called_once_with(str(audio_file), word_timestamps=True)

@patch('clipify.core.audio_processing.whisper.load_model')
def test_transcribe_audio_with_whisper_file_not_found(mock_load_model, tmp_path):
    audio_file_non_existent = tmp_path / "non_existent_audio.wav"
    # File does not exist

    result = audio_processing.transcribe_audio_with_whisper(str(audio_file_non_existent))

    assert result is None
    mock_load_model.assert_not_called() # Model loading shouldn't be attempted if file is not found

@patch('clipify.core.audio_processing.whisper.load_model')
def test_transcribe_audio_with_whisper_transcription_error(mock_load_model, tmp_path):
    mock_model_instance = MagicMock()
    # Simulate an error during the transcribe call
    mock_model_instance.transcribe.side_effect = Exception("Simulated transcription error")
    mock_load_model.return_value = mock_model_instance

    audio_file = tmp_path / "error_audio.wav"
    audio_file.touch()

    result = audio_processing.transcribe_audio_with_whisper(str(audio_file))

    assert result is None # Expect None on transcription error
    mock_load_model.assert_called_once_with("base")
    mock_model_instance.transcribe.assert_called_once_with(str(audio_file), word_timestamps=True)
