"""
test_counterpoint.py
====================
Unit and integration tests for Baroque Fugue Generator contrapuntal logic.
"""

import unittest
from music21 import meter, note, stream

from music_lib import clean_score, read, set_voice
from ofuga import (
    evaluate,
    get_answer,
    inverse,
    judge_my_theme,
    retrograde,
    run_hill_climbing,
)


class TestCounterpoint(unittest.TestCase):
    def setUp(self):
        # Construct a simple, well-formed Baroque subject in C major (4 measures, 4/4)
        self.theme = stream.Part()
        self.theme.append(meter.TimeSignature("4/4"))
        pitches = ["C4", "D4", "E4", "F4", "G4", "E4", "F4", "D4", "C4"]
        for p in pitches:
            self.theme.append(note.Note(p, quarterLength=1.0))

    def test_theme_validation_valid(self):
        """A canonical 4/4 theme starting on tonic within an octave should pass."""
        self.assertTrue(judge_my_theme(self.theme, verbose=False))

    def test_theme_validation_invalid_meter(self):
        """Themes in non-4/4 meters (e.g. 3/4) must be rejected."""
        invalid_theme = stream.Part()
        invalid_theme.append(meter.TimeSignature("3/4"))
        for p in ["C4", "E4", "G4"]:
            invalid_theme.append(note.Note(p, quarterLength=1.0))
        self.assertFalse(judge_my_theme(invalid_theme, verbose=False))

    def test_theme_validation_exceeding_octave(self):
        """Themes with melodic range greater than an octave must be rejected."""
        wide_theme = stream.Part()
        wide_theme.append(meter.TimeSignature("4/4"))
        # Range C3 to E5 is 28 semitones (> 12)
        for p in ["C3", "G4", "E5", "C3"]:
            wide_theme.append(note.Note(p, quarterLength=2.0))
        self.assertFalse(judge_my_theme(wide_theme, verbose=False))

    def test_retrograde_reversal(self):
        """Retrograde must reverse the sequence of notes."""
        rev = retrograde(self.theme)
        orig_notes = [n.pitch.midi for n in self.theme.flatten().notes]
        rev_notes = [n.pitch.midi for n in rev.flatten().notes]
        self.assertEqual(orig_notes, list(reversed(rev_notes)))

    def test_inversion_direction(self):
        """Inversion must mirror the interval direction of the original theme."""
        inv = inverse(self.theme)
        orig_notes = [n.pitch.midi for n in self.theme.flatten().notes]
        inv_notes = [n.pitch.midi for n in inv.flatten().notes]

        orig_first_interval = orig_notes[1] - orig_notes[0]
        inv_first_interval = inv_notes[1] - inv_notes[0]
        self.assertEqual(orig_first_interval, -inv_first_interval)

    def test_answer_generation(self):
        """Answer (comes) should generate notes with transposed starting pitch."""
        ans = get_answer(self.theme)
        notes = list(ans.flatten().notes)
        self.assertGreater(len(notes), 0)
        orig_first = [n.pitch.midi for n in self.theme.flatten().notes][0]
        ans_first = notes[0].pitch.midi
        # Should be transposed by 7 (dominant) or -5 (subdominant/dominant)
        self.assertIn(ans_first - orig_first, [7, -5])

    def test_harmonic_evaluation_consonance_vs_dissonance(self):
        """Consonant vertical intervals must score higher than harsh dissonant clashes."""
        # Consonant score: C4 + E4 (Major third)
        consonant_score = stream.Score()
        p1 = stream.Part()
        p1.append(note.Note("C4", quarterLength=4.0))
        p2 = stream.Part()
        p2.append(note.Note("E4", quarterLength=4.0))
        consonant_score.insert(0.0, p1)
        consonant_score.insert(0.0, p2)

        # Dissonant score: C4 + C#4 (Minor second clash)
        dissonant_score = stream.Score()
        p3 = stream.Part()
        p3.append(note.Note("C4", quarterLength=4.0))
        p4 = stream.Part()
        p4.append(note.Note("C#4", quarterLength=4.0))
        dissonant_score.insert(0.0, p3)
        dissonant_score.insert(0.0, p4)

        score_c = evaluate(consonant_score)
        score_d = evaluate(dissonant_score)
        self.assertGreater(score_c, score_d)

    def test_clean_score_rest_merging(self):
        """clean_score must merge consecutive rests."""
        sc = stream.Score()
        part = stream.Part()
        part.append(note.Rest(quarterLength=1.0))
        part.append(note.Rest(quarterLength=1.0))
        part.append(note.Note("C4", quarterLength=2.0))
        sc.insert(0.0, part)

        cleaned = clean_score(sc)
        rests = list(cleaned.parts[0].getElementsByClass("Rest"))
        self.assertEqual(len(rests), 1)
        self.assertEqual(rests[0].quarterLength, 2.0)

    def test_run_hill_climbing_smoke(self):
        """Smoke test verifying run_hill_climbing produces a valid 2-voice polyphonic score."""
        result = run_hill_climbing(
            self.theme, num_voices=2, n_iterations=2, verbose=False
        )
        self.assertIsInstance(result, stream.Score)
        self.assertEqual(len(result.parts), 2)


if __name__ == "__main__":
    unittest.main()
