# main.py
import argparse
import os
import shutil
import sys

# Assuming clipify package is in PYTHONPATH or installed
try:
    from clipify.core import video_processing, audio_processing, content_analysis, utils
except ImportError:
    # Fallback for direct execution if clipify is not installed (e.g. for development)
    # This allows running main.py directly from the project root
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
    from clipify.core import video_processing, audio_processing, content_analysis, utils

def main_workflow(args):
    print(f"Starting Clipify workflow with args: {args}")

    # Create output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        print(f"Created output directory: {args.output_dir}")

    # Temporary directory for intermediate files
    temp_dir = os.path.join(args.output_dir, '.clipify_temp')
    os.makedirs(temp_dir, exist_ok=True)
    print(f"Using temporary directory: {temp_dir}")

    video_file_path = None # Initialize
    original_video_filename = os.path.basename(args.input_source)


    # --- STAGE 1: Handle Input ---
    print("\n--- STAGE 1: Handling Input ---")
    try:
        if args.input_source.startswith('http://') or args.input_source.startswith('https://'):
            print(f"Input is a URL: {args.input_source}. Downloading...")
            video_file_path = utils.download_youtube_video(args.input_source, output_path=temp_dir)
            if video_file_path:
                print(f"Video downloaded successfully to: {video_file_path}")
                original_video_filename = os.path.basename(video_file_path) # Update filename from downloaded
            else:
                print(f"Failed to download video from URL: {args.input_source}")
                return # Exit if download fails
        else:
            print(f"Input is a local file: {args.input_source}")
            if not os.path.exists(args.input_source):
                print(f"Error: Local video file not found at {args.input_source}")
                return # Exit if local file not found

            # Copy local file to temp_dir for consistent processing
            base_name = os.path.basename(args.input_source)
            video_file_path = os.path.join(temp_dir, base_name)
            shutil.copy(args.input_source, video_file_path)
            print(f"Copied local video to temporary location: {video_file_path}")

        if not video_file_path or not os.path.exists(video_file_path):
            print("Error: Video file path not obtained or file does not exist after input handling.")
            return
    except Exception as e:
        print(f"An error occurred during input handling: {e}")
        return

    print(f"Proceeding with video file: {video_file_path}")

    # --- STAGE 2: Audio Extraction ---
    print("\n--- STAGE 2: Extracting Audio ---")
    extracted_audio_path = None # Initialize
    try:
        # Define audio file path based on the (potentially downloaded) video's name
        audio_file_name = f"{os.path.splitext(original_video_filename)[0]}.wav"
        audio_file_path_temp = os.path.join(temp_dir, audio_file_name)

        extracted_audio_path = audio_processing.extract_audio_from_video(video_file_path, output_audio_path=audio_file_path_temp)
        if not extracted_audio_path:
            print("Error: Audio extraction failed.")
            # Optional: cleanup temp_dir if desired before exiting
            # if not args.keep_intermediate_files: shutil.rmtree(temp_dir)
            return
        print(f"Audio extracted successfully to: {extracted_audio_path}")
    except Exception as e:
        print(f"An error occurred during audio extraction: {e}")
        # Optional: cleanup temp_dir
        return

    # --- STAGE 3: Transcription ---
    print("\n--- STAGE 3: Transcribing Audio ---")
    transcription_result = None # Initialize
    try:
        transcription_result = audio_processing.transcribe_audio_with_whisper(extracted_audio_path)
        if not transcription_result or 'text' not in transcription_result:
            print("Error: Transcription failed or returned unexpected result.")
            # Optional: cleanup temp_dir
            return
        # Limit printing potentially very long transcripts
        transcript_preview = transcription_result['text'][:150].replace('\n', ' ') + "..." if len(transcription_result['text']) > 150 else transcription_result['text'].replace('\n', ' ')
        print(f"Transcription complete. Transcript preview: {transcript_preview}")
        # print(f"Full transcription result keys: {transcription_result.keys()}") # For debugging if needed
    except Exception as e:
        print(f"An error occurred during transcription: {e}")
        # Optional: cleanup temp_dir
        return

    # --- STAGE 4: Content Analysis (Identify Key Segments) ---
    print("\n--- STAGE 4: Identifying Key Segments ---")
    selected_segments = []
    try:
        if 'segments' not in transcription_result or not transcription_result['segments']:
            print("No transcription segments found to analyze.")
        else:
            selected_segments = content_analysis.find_important_segments(
                transcription_segments=transcription_result['segments'],
                num_segments=args.num_segments,
                min_segment_duration=float(args.min_segment_length)
            )
            if not selected_segments:
                print("No suitable segments found after content analysis.")
            else:
                print(f"Found {len(selected_segments)} key segments:")
                for i, seg in enumerate(selected_segments):
                    print(f"  Segment {i+1}: Start={seg['start']:.2f}s, End={seg['end']:.2f}s, Text='{seg['text'][:50]}...'")
    except Exception as e:
        print(f"An error occurred during content analysis: {e}")
        # Continue without segments or decide to return
        selected_segments = [] # Ensure it's an empty list on error


    # --- STAGE 5: Video Segment Extraction ---
    print("\n--- STAGE 5: Extracting Video Segments ---")
    extracted_clips_info = [] # Will store dicts with info about extracted clips

    if not selected_segments:
        print("No segments selected for extraction. Skipping Stage 5.")
    else:
        raw_clips_dir = os.path.join(args.output_dir, 'raw_clips')
        os.makedirs(raw_clips_dir, exist_ok=True)
        print(f"Saving raw extracted clips to: {raw_clips_dir}")

        for i, segment_info in enumerate(selected_segments):
            try:
                start_time_s = segment_info['start']
                end_time_s = segment_info['end']

                # Sanitize filename components (simple version)
                text_preview_for_filename = "".join(c if c.isalnum() else "_" for c in segment_info['text'][:20]).strip('_')
                segment_base_name = f"segment_{i+1}_{text_preview_for_filename}_{start_time_s:.0f}s-{end_time_s:.0f}s.mp4"
                extracted_segment_output_path = os.path.join(raw_clips_dir, segment_base_name)

                print(f"Extracting segment {i+1}/{len(selected_segments)}: {segment_base_name} (From {start_time_s:.2f}s to {end_time_s:.2f}s)")

                # video_file_path is the path to the video in .clipify_temp directory
                success = video_processing.extract_video_segments(
                    video_file_path=video_file_path,
                    start_seconds=start_time_s,
                    end_seconds=end_time_s,
                    output_file_path=extracted_segment_output_path
                )

                if success:
                    segment_info['raw_clip_path'] = extracted_segment_output_path
                    extracted_clips_info.append(segment_info) # Add successful ones to new list
                    print(f"Successfully extracted: {extracted_segment_output_path}")
                else:
                    print(f"Failed to extract segment {i+1}: {segment_base_name}")

            except Exception as e:
                print(f"An error occurred during extraction of segment {i+1}: {e}")
                # Continue to next segment if one fails

    # Update selected_segments to only include those that were successfully extracted
    selected_segments = extracted_clips_info # This now contains segments with 'raw_clip_path'

    # --- STAGE 6: Video Formatting & Captioning ---
    print("\n--- STAGE 6: Formatting and Captioning Segments ---")
    processed_clips_info = [] # Will store info about fully processed clips

    if not selected_segments:
        print("No segments available for formatting/captioning. Skipping Stage 6.")
    else:
        final_clips_dir = os.path.join(args.output_dir, 'final_clips')
        os.makedirs(final_clips_dir, exist_ok=True)
        print(f"Saving final processed clips to: {final_clips_dir}")

        for i, segment_data in enumerate(selected_segments):
            raw_clip_input_path = segment_data.get('raw_clip_path')
            if not raw_clip_input_path or not os.path.exists(raw_clip_input_path):
                print(f"Skipping segment {i+1} due to missing raw clip path or file: {raw_clip_input_path}")
                continue

            print(f"\nProcessing final output for segment {i+1}/{len(selected_segments)}: {os.path.basename(raw_clip_input_path)}")

            base_name_no_ext = os.path.splitext(os.path.basename(raw_clip_input_path))[0]

            # 1. Convert Aspect Ratio
            formatted_aspect_path = os.path.join(final_clips_dir, f"{base_name_no_ext}_formatted.mp4")
            print(f"  Converting aspect ratio to {args.output_aspect_ratio} -> {formatted_aspect_path}")
            converted_path = video_processing.convert_video_aspect_ratio(
                raw_clip_input_path,
                formatted_aspect_path,
                args.output_aspect_ratio
            )

            if not converted_path:
                print(f"  Failed to convert aspect ratio for {raw_clip_input_path}. Skipping further processing for this segment.")
                continue

            current_processed_path = converted_path

            # 2. Add Captions (if not skipped)
            if not args.skip_captioning:
                captioned_output_path = os.path.join(final_clips_dir, f"{base_name_no_ext}_captioned.mp4")
                print(f"  Adding captions -> {captioned_output_path}")

                # Filter main transcription_result['segments'] for those relevant to the current video segment
                # These are Whisper's original segments, not the 'selected_segments' from content_analysis initially
                relevant_whisper_segments = [
                    ws for ws in transcription_result.get('segments', [])
                    if ws['start'] < segment_data['end'] and ws['end'] > segment_data['start']
                ]

                adjusted_transcription_segments = []
                for ws in relevant_whisper_segments:
                    # Adjust timestamps to be relative to the start of the current extracted segment
                    # Ensure text is present
                    text = ws.get('text', '').strip()
                    if not text:
                        continue

                    new_start = max(0, ws['start'] - segment_data['start'])
                    new_end = ws['end'] - segment_data['start']

                    # Only include if the segment has positive duration within the clip
                    if new_end > new_start:
                        adjusted_transcription_segments.append({
                            'text': text,
                            'start': new_start,
                            'end': new_end
                        })

                if not adjusted_transcription_segments:
                    print(f"  No relevant transcription segments found for captioning {os.path.basename(current_processed_path)}")
                else:
                    # add_captions_to_video returns None on error, path on success (implicit in problem statement, but good to note)
                    # For this subtask, let's assume it modifies in place or returns the output path.
                    # The function provided in a previous subtask saves to output_path and doesn't return.
                    video_processing.add_captions_to_video(
                        current_processed_path, # Input is the aspect-ratio-converted video
                        adjusted_transcription_segments,
                        captioned_output_path # Output is the new captioned video
                    )
                    # Check if captioning was successful by seeing if the file exists
                    if os.path.exists(captioned_output_path):
                         # If captioning created a new file and previous formatted file still exists (and shouldn't be kept as final)
                        if current_processed_path != captioned_output_path and os.path.exists(current_processed_path) and not args.keep_intermediate_files :
                            try:
                                # This logic might be too aggressive if current_processed_path IS the final_clips_dir path
                                # Only remove if it's truly an intermediate step that was superseded by captioning.
                                # The current structure saves formatted then captioned to final_clips_dir, so this is more about
                                # cleaning up the _formatted.mp4 if _captioned.mp4 is made.
                                if "_formatted" in os.path.basename(current_processed_path): # Heuristic
                                     print(f"  Removing intermediate formatted file: {current_processed_path}")
                                     os.remove(current_processed_path)
                            except OSError as e:
                                print(f"  Warning: Could not remove intermediate formatted file {current_processed_path}: {e}")
                        current_processed_path = captioned_output_path
                        print(f"  Successfully added captions: {current_processed_path}")
                    else:
                        print(f"  Captioning seems to have failed for {os.path.basename(current_processed_path)} (output file {captioned_output_path} not found). Using uncaptioned version.")

            segment_data['final_clip_path'] = current_processed_path
            processed_clips_info.append(segment_data)
            print(f"  Finished processing segment. Final output: {current_processed_path}")

    # Update selected_segments to only include those that were successfully processed through Stage 6
    selected_segments = processed_clips_info
    final_segment_paths = [s['final_clip_path'] for s in selected_segments if 'final_clip_path' in s and s['final_clip_path']]


    # --- STAGE 5 & 6: Video Segment Extraction, Formatting, and Captioning ---
    # Commenting out the old placeholder structure for stage 5 & 6
    # final_segment_paths = []
    # # TODO: Loop through important_segments (using transcription_result which includes word timestamps)
    # # for i, seg_info in enumerate(important_segments):
    # #   start_time_str = utils.format_time(seg_info['start_seconds'])
    # #   end_time_str = utils.format_time(seg_info['end_seconds'])
    # #   segment_base_name = f"segment_{i+1}_{start_time_str.replace(':','-')}_{end_time_str.replace(':','-')}.mp4"
    # #
    # #   raw_extracted_segment_path = os.path.join(intermediate_files_dir, f"raw_{segment_base_name}") # This was old temp dir
    # #   video_processing.extract_video_segments(video_file_path, start_time_s, end_time_s, raw_extracted_segment_path) # Adjusted call
    # #
    # #   formatted_segment_path = os.path.join(args.output_dir, f"formatted_{segment_base_name}")
    # #   video_processing.convert_video_aspect_ratio(raw_extracted_segment_path, formatted_segment_path, target_aspect_ratio=args.output_aspect_ratio) # Assuming convert_video_aspect_ratio takes target_aspect_ratio
    # #
    # #   if not args.skip_captioning:
    # #       # Need to get relevant transcription parts for this specific segment
    # #       # This requires filtering transcription_result['segments'] or ['words'] based on seg_info['start_seconds'] and seg_info['end_seconds']
    # #       # And then adjusting timestamps to be relative to the start of the extracted segment.
    # #       # relevant_transcription_for_segment = filter_and_adjust_timestamps(transcription_result, seg_info['start_seconds'], seg_info['end_seconds'])
    # #       captioned_segment_path = os.path.join(args.output_dir, f"captioned_{segment_base_name}")
    # #       video_processing.add_captions_to_video(formatted_segment_path, relevant_transcription_for_segment, captioned_segment_path)
    # #       final_segment_paths.append(captioned_segment_path)
    # #       if formatted_segment_path != captioned_segment_path and args.keep_intermediate_files == False and os.path.exists(formatted_segment_path):
    # #           os.remove(formatted_segment_path) # remove intermediate formatted if captioning is done to different file
    # #   else:
    # #       final_segment_paths.append(formatted_segment_path)
    # print("Video segment extraction, formatting, and captioning placeholder") # Old placeholder

    # --- STAGE 7: Cleanup ---
    # Ensure raw_clips_dir is defined for cleanup, even if Stage 5 was skipped
    raw_clips_dir = os.path.join(args.output_dir, 'raw_clips')

    if not args.keep_intermediate_files:
        print(f"\n--- STAGE 7: Cleaning Up Intermediate Files ---")
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"Successfully removed temporary directory: {temp_dir}")
            else:
                print(f"Temporary directory not found, skipping removal: {temp_dir}")

            if os.path.exists(raw_clips_dir):
                 # Check if raw_clips_dir is different from final_clips_dir to avoid deleting final clips
                 # This check is implicitly handled if final_clips are in a different folder.
                 # If they could be the same, more careful logic would be needed.
                 # For now, assuming they are different if raw_clips_dir exists and keep_intermediate_files is false.
                shutil.rmtree(raw_clips_dir)
                print(f"Successfully removed raw clips directory: {raw_clips_dir}")
            else:
                print(f"Raw clips directory not found, skipping removal: {raw_clips_dir}")

        except OSError as e:
            print(f"Error during cleanup: {e.strerror}")
    else:
        print(f"\n--- STAGE 7: Keeping Intermediate Files ---")
        print(f"Intermediate files kept in: {temp_dir}")
        if os.path.exists(raw_clips_dir):
            print(f"Raw extracted clips kept in: {raw_clips_dir}")


    print(f"\nClipify workflow completed. Final clips are in: {os.path.join(args.output_dir, 'final_clips') if final_segment_paths else 'N/A'}")
    if final_segment_paths:
        print("Generated clips:")
        for fp in final_segment_paths:
            print(f"  - {fp}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Clipify: Transform long videos into engaging short clips.')
    parser.add_argument('input_source', type=str, help='Path to a local video file or a YouTube URL.')
    parser.add_argument('output_dir', type=str, help='Directory to save the processed clips.')

    parser.add_argument('--num_segments', type=int, default=3, help='Number of key segments to extract (default: 3).')
    parser.add_argument('--min_segment_length', type=int, default=30, help='Minimum seconds for each segment (default: 30).')
    parser.add_argument('--output_aspect_ratio', type=str, default='9:16', help="Target aspect ratio (e.g., '9:16', '1:1', default: '9:16').")

    parser.add_argument('--skip_captioning', action='store_true', help='Skip adding captions to the video segments.')
    parser.add_argument('--keep_intermediate_files', action='store_true', help='Keep all intermediate files (e.g., downloaded video, extracted audio).')

    args = parser.parse_args()
    main_workflow(args)
