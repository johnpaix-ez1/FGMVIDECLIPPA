import spacy
# import nltk # No longer strictly needed for the current version of find_important_segments or its fallback
# from nltk.tokenize import sent_tokenize # No longer strictly needed
# from .utils import format_time # format_time is not used

# NLTK download block removed as sent_tokenize is not currently used.
# If re-introduced, this would be needed:
# # TODO: Handle NLTK resource download more gracefully (e.g., during setup or first run)
# try:
#     nltk.data.find('tokenizers/punkt')
# except nltk.downloader.DownloadError:
#     nltk.download('punkt')

def split_transcript_by_timestamps(transcription_result, interval=60):
    """Splits a transcript into segments based on timestamps and a given interval."""
    segments_text_time = []
    current_segment_texts = []
    current_segment_start_time = None
    last_word_end_time = 0

    if not transcription_result or 'segments' not in transcription_result:
        return []

    for segment_info in transcription_result['segments']:
        segment_start_time = segment_info['start']
        segment_end_time = segment_info['end']
        segment_text = segment_info['text']

        if current_segment_start_time is None:
            current_segment_start_time = segment_start_time

        # If the gap between the last word and the current segment start is too large,
        # or if adding this segment would make the current combined segment too long (hypothetically),
        # then finalize the current segment and start a new one.
        # This logic is a bit simplified; actual segment duration is based on word timestamps.

        # Iterate through words for more precise timing if available
        if 'words' in segment_info:
            for word_info in segment_info['words']:
                word_start_time = word_info['start']
                word_end_time = word_info['end']
                word_text = word_info['text']

                if current_segment_start_time is None: # Should have been set by segment start
                     current_segment_start_time = word_start_time

                # Check for large gap or if current word extends beyond interval from current_segment_start_time
                if (word_start_time - last_word_end_time > interval / 2 and last_word_end_time != 0) or \
                   (word_end_time - current_segment_start_time > interval):
                    if current_segment_texts:
                        segments_text_time.append({
                            "time": f"{format_time(current_segment_start_time)} - {format_time(last_word_end_time)}",
                            "text": "".join(current_segment_texts)
                        })
                        current_segment_texts = []
                    current_segment_start_time = word_start_time

                current_segment_texts.append(word_text)
                last_word_end_time = word_end_time
        else: # Fallback to segment-level timing if word timestamps are not available
            if (segment_start_time - last_word_end_time > interval / 2 and last_word_end_time != 0) or \
               (segment_end_time - current_segment_start_time > interval):
                if current_segment_texts: # current_segment_texts might be empty if previous was just one segment
                    segments_text_time.append({
                        "time": f"{format_time(current_segment_start_time)} - {format_time(last_word_end_time if last_word_end_time > current_segment_start_time else segment_start_time)}",
                        "text": "".join(current_segment_texts)
                    })
                    current_segment_texts = []
                current_segment_start_time = segment_start_time

            current_segment_texts.append(segment_text)
            last_word_end_time = segment_end_time


    # Add any remaining text as the last segment
    if current_segment_texts:
        segments_text_time.append({
            "time": f"{format_time(current_segment_start_time)} - {format_time(last_word_end_time)}",
            "text": "".join(current_segment_texts)
        })

    return segments_text_time


def _find_important_segments_basic(transcription_segments: list, num_segments: int, min_segment_duration: float) -> list:
    """
    Basic segment selection based on text length and duration.
    (This was the previous implementation of find_important_segments)
    """
    if not transcription_segments:
        return []

    valid_segments = []
    for seg in transcription_segments:
        duration = seg.get('end', 0.0) - seg.get('start', 0.0)
        if duration >= min_segment_duration and seg.get('text', '').strip():
            valid_segments.append({
                'text': seg['text'].strip(),
                'start': seg['start'],
                'end': seg['end'],
                'duration': duration,
                'text_length': len(seg['text'].strip())
            })

    valid_segments.sort(key=lambda x: x['text_length'], reverse=True)
    selected_segments = valid_segments[:num_segments]
    selected_segments.sort(key=lambda x: x['start'])
    return [{'text': s['text'], 'start': s['start'], 'end': s['end']} for s in selected_segments]


def find_important_segments(transcription_segments: list, num_segments: int, min_segment_duration: float) -> list:
    """
    Identifies important segments from Whisper's transcription segments using spaCy for scoring,
    with a fallback to basic text-length based selection if spaCy model is unavailable.

    Args:
        transcription_segments (list): List of segment dictionaries from Whisper.
        num_segments (int): The desired number of important segments.
        min_segment_duration (float): Minimum duration for a segment to be considered.

    Returns:
        list: A list of dictionaries, each representing an important segment.
    """
    try:
        nlp = spacy.load('en_core_web_sm')
        print("Using spaCy for segment importance scoring.")
    except OSError:
        print("spaCy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'.")
        print("Falling back to basic segment selection based on text length.")
        return _find_important_segments_basic(transcription_segments, num_segments, min_segment_duration)
    except Exception as e: # Catch other potential spacy loading errors
        print(f"An unexpected error occurred while loading spaCy model: {e}")
        print("Falling back to basic segment selection based on text length.")
        return _find_important_segments_basic(transcription_segments, num_segments, min_segment_duration)


    if not transcription_segments:
        return []

    scored_segments = []
    for segment_data in transcription_segments:
        text = segment_data.get('text', '').strip()
        start_time = segment_data.get('start')
        end_time = segment_data.get('end')

        if not (text and start_time is not None and end_time is not None):
            continue

        doc = nlp(text)
        # Score based on number of nouns, proper nouns, and verbs
        score = len([token for token in doc if token.pos_ in ['NOUN', 'PROPN', 'VERB']])

        scored_segments.append({
            'text': text,
            'start': start_time,
            'end': end_time,
            'original_score': score,
            'duration': end_time - start_time
        })

    # Filter by minimum duration
    candidate_segments = [
        seg for seg in scored_segments if seg['duration'] >= min_segment_duration
    ]

    if not candidate_segments:
        print("No segments meet the minimum duration criteria after spaCy scoring.")
        return []

    # Sort by original_score (descending)
    candidate_segments.sort(key=lambda x: x['original_score'], reverse=True)

    # Select top num_segments
    top_segments = candidate_segments[:num_segments]

    # Sort selected segments by start time (chronological order)
    top_segments.sort(key=lambda x: x['start'])

    # Return only the required keys
    return [{'text': s['text'], 'start': s['start'], 'end': s['end']} for s in top_segments]
