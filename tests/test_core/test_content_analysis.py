# tests/test_core/test_content_analysis.py
import pytest
from clipify.core import content_analysis
from unittest.mock import patch, MagicMock

# Mock spaCy token for simulating POS tags
class MockSpacyToken:
    def __init__(self, pos_):
        self.pos_ = pos_

# Mock spaCy Doc object
class MockSpacyDoc:
    def __init__(self, tokens_pos_list):
        self.tokens = [MockSpacyToken(pos) for pos in tokens_pos_list]

    def __iter__(self): # Allows iterating over doc.tokens in the list comprehension
        return iter(self.tokens)

    def __len__(self): # In case len(doc) is used somewhere, though not in current SUT
        return len(self.tokens)


@patch('clipify.core.content_analysis.spacy.load')
def test_find_important_segments_spacy_path_success(mock_spacy_load, tmp_path):
    mock_nlp = MagicMock()

    # Define a side_effect function for nlp()
    def nlp_side_effect(text):
        if 'important' in text and 'stuff' in text: # Segment 1
            return MockSpacyDoc(['NOUN', 'VERB', 'PROPN', 'NOUN']) # Score 4
        elif 'Less' in text: # Segment 2
            return MockSpacyDoc(['ADJ', 'CCONJ']) # Score 0
        elif 'Very important' in text: # Segment 3
            return MockSpacyDoc(['ADV', 'NOUN', 'VERB', 'PROPN', 'VERB', 'NOUN']) # Score 5
        elif 'Short one' in text: # Segment 4 (too short duration)
             return MockSpacyDoc(['NOUN', 'NOUN']) # Score 2
        elif 'Another important' in text: # Segment 5
             return MockSpacyDoc(['DET', 'NOUN', 'ADJ', 'PROPN']) # Score 2
        return MockSpacyDoc([]) # Default empty doc

    mock_nlp.side_effect = nlp_side_effect
    mock_spacy_load.return_value = mock_nlp

    transcription_segments = [
        {'text': 'This is important stuff', 'start': 0.0, 'end': 5.0},   # Duration 5.0, Score 4
        {'text': 'Less so, not much here', 'start': 6.0, 'end': 10.0},  # Duration 4.0, Score 0
        {'text': 'Very important indeed, yes', 'start': 11.0, 'end': 20.0},# Duration 9.0, Score 5
        {'text': 'Short one', 'start': 21.0, 'end': 22.0},               # Duration 1.0, Score 2 (too short)
        {'text': 'Another important segment', 'start': 23.0, 'end': 30.0} # Duration 7.0, Score 2
    ]
    num_segments_to_select = 2
    min_segment_duration = 4.0

    selected = content_analysis.find_important_segments(
        transcription_segments, num_segments_to_select, min_segment_duration
    )

    assert len(selected) == 2
    # Expected order after filtering by duration, sorting by score (desc), taking top 2, then sorting by time (asc):
    # 1. Segment 3 ('Very important...'): Score 5, Duration 9.0
    # 2. Segment 1 ('This is important...'): Score 4, Duration 5.0
    # (Segment 5 ('Another important...') with Score 2, Duration 7.0 would be next if num_segments=3)

    # After final sort by start time:
    assert selected[0]['text'] == 'This is important stuff'
    assert selected[0]['start'] == 0.0
    assert selected[1]['text'] == 'Very important indeed, yes'
    assert selected[1]['start'] == 11.0

    mock_spacy_load.assert_called_once_with('en_core_web_sm')

@patch('clipify.core.content_analysis.spacy.load')
@patch('clipify.core.content_analysis._find_important_segments_basic')
def test_find_important_segments_spacy_model_not_found_fallback(mock_basic_selector, mock_spacy_load):
    mock_spacy_load.side_effect = OSError("Mocked OSError: Model not found") # Simulate model not found

    # Define what the basic selector should return for this test case
    fallback_return_value = [{'text': 'fallback segment', 'start': 0, 'end': 10}]
    mock_basic_selector.return_value = fallback_return_value

    trans_segments_input = [{'text': 'some text', 'start': 0, 'end': 10}]
    num_segments_input = 1
    min_duration_input = 5.0

    result = content_analysis.find_important_segments(trans_segments_input, num_segments_input, min_duration_input)

    mock_spacy_load.assert_called_once_with('en_core_web_sm')
    mock_basic_selector.assert_called_once_with(trans_segments_input, num_segments_input, min_duration_input)
    assert result == fallback_return_value

def test_find_important_segments_basic_logic_direct():
    """
    Tests the _find_important_segments_basic function directly.
    This ensures the fallback mechanism has a well-tested alternative.
    """
    segments_input = [
        {'text': 'Short', 'start': 0.0, 'end': 1.0},                            # Duration 1.0, Length 5
        {'text': 'Medium length segment', 'start': 2.0, 'end': 5.0},            # Duration 3.0, Length 21
        {'text': 'This is a very long segment indeed', 'start': 6.0, 'end': 12.0} # Duration 6.0, Length 34
    ]

    # Test 1: Select 1 segment, min duration 3.0
    # Expected: 'This is a very long segment indeed' (longest text, meets duration)
    selected_1 = content_analysis._find_important_segments_basic(segments_input, 1, 3.0)
    assert len(selected_1) == 1
    assert selected_1[0]['text'] == 'This is a very long segment indeed'

    # Test 2: Select 2 segments, min duration 3.0
    # Expected: Longest two by text that meet duration, then sorted by start time
    # 1. 'This is a very long segment indeed' (Length 34)
    # 2. 'Medium length segment' (Length 21)
    selected_2 = content_analysis._find_important_segments_basic(segments_input, 2, 3.0)
    assert len(selected_2) == 2
    # After sorting by text_length desc, then by start time asc:
    assert selected_2[0]['text'] == 'Medium length segment' # start 2.0
    assert selected_2[1]['text'] == 'This is a very long segment indeed' # start 6.0

    # Test 3: Select 1 segment, min duration 7.0 (none should meet this)
    selected_3 = content_analysis._find_important_segments_basic(segments_input, 1, 7.0)
    assert len(selected_3) == 0

    # Test 4: Empty input
    selected_4 = content_analysis._find_important_segments_basic([], 1, 1.0)
    assert len(selected_4) == 0

    # Test 5: num_segments is more than available valid segments
    segments_input_2 = [
        {'text': 'Segment A meets duration', 'start': 0.0, 'end': 5.0}, # Duration 5.0
        {'text': 'Segment B too short', 'start': 6.0, 'end': 7.0}       # Duration 1.0
    ]
    selected_5 = content_analysis._find_important_segments_basic(segments_input_2, 2, 3.0)
    assert len(selected_5) == 1
    assert selected_5[0]['text'] == 'Segment A meets duration'
