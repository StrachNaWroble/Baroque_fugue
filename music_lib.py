"""
music_lib.py
============
Core musical manipulation library for Baroque polyphony and counterpoint.

Provides utilities for:
- Score ingestion across multiple formats (.mscz, .musicxml, .mid).
- Counterpoint constraint checking (consonance vs. dissonance, parallel 5ths & 8ths).
- Chromatic conflict resolution (shifting clashing notes to consonant degrees).
- Voice allocation, rest compaction, and grand staff organ score condensation.
"""

import copy
import os
import shutil
import subprocess
import tempfile
from typing import Optional, Union
from music21 import (
    clef,
    converter,
    instrument,
    interval,
    key,
    meter,
    note,
    pitch,
    stream,
)


def _find_musescore_binary() -> Optional[str]:
    """Locate the MuseScore executable on the current system."""
    for binary_name in ["musescore3", "musescore", "mscore"]:
        found = shutil.which(binary_name)
        if found:
            return found
    return None


def read(file_name: str) -> stream.Score:
    """
    Parse a musical score from a file into a music21 Score.

    Supports:
    - .mscz (via automated MuseScore conversion to MusicXML)
    - .musicxml, .xml, .mxl (direct parsing)
    - .mid, .midi (direct parsing)

    Parameters
    ----------
    file_name : str
        Path to the score file.

    Returns
    -------
    stream.Score
        Parsed music21 Score instance.
    """
    if not os.path.exists(file_name):
        raise FileNotFoundError(f"Score file not found: {file_name}")

    ext = os.path.splitext(file_name)[1].lower()

    if ext == ".mscz":
        musescore_bin = _find_musescore_binary()
        if not musescore_bin:
            raise RuntimeError(
                f"MuseScore executable ('musescore3' or 'musescore') is required to convert '{file_name}'. "
                "Please install MuseScore or pass a .musicxml / .mid file directly."
            )

        with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as tmp_file:
            tmp_xml = tmp_file.name

        try:
            cmd = [musescore_bin, file_name, "-o", tmp_xml]
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            score = converter.parse(tmp_xml)
        finally:
            if os.path.exists(tmp_xml):
                os.remove(tmp_xml)
        return score
    else:
        return converter.parse(file_name)


def set_voice(part: stream.Stream, p: float = 0.0) -> stream.Part:
    """
    Standardize a musical part for polyphonic organ voicing with an optional time offset.

    Parameters
    ----------
    part : stream.Stream
        Input melodic stream or part.
    p : float
        Temporal offset in quarter note lengths (beats) before the voice enters.

    Returns
    -------
    stream.Part
        Configured Part with organ timbre, treble clef, meter, and offset.
    """
    fixed_part = stream.Part()
    fixed_part.insert(0.0, instrument.PipeOrgan())
    fixed_part.insert(0.0, clef.TrebleClef())
    fixed_part.insert(0.0, meter.TimeSignature("4/4"))

    part_flat = part.flatten()
    key_sigs = part_flat.getElementsByClass("KeySignature")
    if key_sigs:
        fixed_part.insert(0.0, copy.deepcopy(key_sigs[0]))
    else:
        fixed_part.insert(0.0, key.KeySignature(0))

    if p > 0:
        fixed_part.insert(0.0, note.Rest(quarterLength=p))

    for element in part_flat.notesAndRests:
        fixed_part.insert(p + element.offset, copy.deepcopy(element))

    return fixed_part


def clean_dissonances(
    ref_part: stream.Stream, target_part: stream.Stream, p: float = 0.0
) -> stream.Stream:
    """
    Filter out severe harmonic dissonances and forbidden parallel intervals.

    Rules applied:
    - Eliminate dissonant vertical intervals.
    - Treat parallel perfect 5ths ('P5') and parallel octaves ('P8') as forbidden.
    - Treat perfect 4ths ('P4') and unisons ('P1') as non-permitted collisions.
    - Replace forbidden notes in target_part with rests.

    Parameters
    ----------
    ref_part : stream.Stream
        Reference voice against which intervals are checked.
    target_part : stream.Stream
        Candidate voice being filtered.
    p : float
        Temporal offset of target_part relative to ref_part.

    Returns
    -------
    stream.Stream
        Dissonance-cleaned stream.
    """
    ref_flat = ref_part.flatten()
    target_flat = target_part.flatten()

    cleaned_target = target_part.__class__()

    for el in target_flat.getElementsByClass(
        ["TimeSignature", "KeySignature", "Clef", "Instrument"]
    ):
        cleaned_target.insert(0.0, copy.deepcopy(el))

    ref_notes = list(ref_flat.notes)
    prev_interval = None

    for tgt_el in target_flat.notesAndRests:
        if not tgt_el.isNote:
            cleaned_target.insert(tgt_el.offset, copy.deepcopy(tgt_el))
            continue

        absolute_time = tgt_el.offset + p
        concurrent_ref_notes = [
            n
            for n in ref_notes
            if max(n.offset, absolute_time)
            < min(n.offset + n.quarterLength, absolute_time + tgt_el.quarterLength)
        ]

        is_bad = False

        if concurrent_ref_notes:
            for ref_note in concurrent_ref_notes:
                inter = interval.Interval(ref_note, tgt_el)

                if not inter.isConsonant():
                    is_bad = True
                elif inter.simpleName in ["P4", "P1"]:
                    is_bad = True
                elif inter.simpleName in ["P5", "P8"]:
                    if inter.simpleName == prev_interval:
                        is_bad = True

                if is_bad:
                    break

            if not is_bad:
                prev_interval = interval.Interval(
                    concurrent_ref_notes[-1], tgt_el
                ).simpleName

        if is_bad:
            cleaned_target.insert(
                tgt_el.offset, note.Rest(quarterLength=tgt_el.quarterLength)
            )
        else:
            cleaned_target.insert(tgt_el.offset, copy.deepcopy(tgt_el))

    return cleaned_target


def merge(
    part1: stream.Stream, part2: stream.Stream, p: Optional[float] = None
) -> stream.Score:
    """
    Merge two parts into a Score, applying dissonance cleaning.

    Parameters
    ----------
    part1 : stream.Stream
        First voice.
    part2 : stream.Stream
        Second voice.
    p : Optional[float]
        Offset for part2. Defaults to part1.highestTime.

    Returns
    -------
    stream.Score
        Merged 2-part score.
    """
    part1 = part1.flatten()
    part2 = part2.flatten()

    if p is None:
        p = part1.highestTime

    part2_cleaned = clean_dissonances(part1, part2, p)

    score = stream.Score()
    score.insert(0.0, set_voice(part1, 0.0))
    score.insert(0.0, set_voice(part2_cleaned, p))
    return score


def add_voice_to_score(
    existing_score: stream.Score, new_voice: stream.Stream, p: float
) -> stream.Score:
    """
    Add a new candidate voice at offset `p`, resolving chromatic conflicts.

    When concurrent notes collide into harsh dissonances (seconds, tritones,
    sevenths, unisons), the candidate note's MIDI pitch is locally shifted by the
    minimal semitone interval to find the nearest consonant pitch.

    Parameters
    ----------
    existing_score : stream.Score
        Polyphonic score containing previously accepted voices.
    new_voice : stream.Stream
        New melody/voice to integrate.
    p : float
        Temporal entry offset in quarter lengths.

    Returns
    -------
    stream.Score
        Updated score with the newly integrated voice.
    """
    prepared_new_voice = set_voice(new_voice, p)
    existing_notes = list(existing_score.flatten().notes)

    for n in prepared_new_voice.notes:
        if not n.isNote:
            continue

        n_start = n.offset
        n_end = n_start + n.quarterLength

        concurrent_notes = []
        for ex_n in existing_notes:
            if (
                max(n_start, ex_n.offset)
                < min(n_end, ex_n.offset + ex_n.quarterLength) - 0.001
            ):
                if ex_n.isNote:
                    concurrent_notes.append(ex_n)
                elif ex_n.isChord:
                    concurrent_notes.extend(ex_n.pitches)

        if not concurrent_notes:
            continue

        def is_dissonant(pitch_to_check):
            midi_check = (
                pitch_to_check.midi
                if hasattr(pitch_to_check, "midi")
                else pitch_to_check
            )
            for ex_n in concurrent_notes:
                try:
                    p_ex_midi = (
                        ex_n.pitch.midi
                        if hasattr(ex_n, "pitch")
                        else ex_n.midi
                    )
                    diff = abs(p_ex_midi - midi_check)
                    m = diff % 12
                    # Dissonant intervals: unison (0), m2/M2 (1, 2), tritone (6), m7/M7 (10, 11)
                    if diff == 0 or m in [1, 2, 6, 10, 11]:
                        return True
                except Exception:
                    pass
            return False

        if is_dissonant(n.pitch):
            original_midi = n.pitch.midi
            best_shift = None

            shifts = []
            for i in range(1, 13):
                shifts.append(i)
                shifts.append(-i)

            for shift in shifts:
                test_pitch = pitch.Pitch()
                test_pitch.midi = original_midi + shift
                if not is_dissonant(test_pitch):
                    best_shift = shift
                    break

            if best_shift is not None:
                n.pitch.midi = original_midi + best_shift

    new_score = stream.Score()
    for part in existing_score.parts:
        new_score.insert(0.0, copy.deepcopy(part))
    new_score.insert(0.0, prepared_new_voice)

    return new_score


def combine_parts_to_voices(score: stream.Score) -> stream.Score:
    """
    Combine pairs of single-line parts into two-voice staves for organ/keyboard notation.

    Parameters
    ----------
    score : stream.Score
        Score with multiple independent parts.

    Returns
    -------
    stream.Score
        Condensed score with paired voices per staff.
    """
    condensed_score = stream.Score()
    parts = list(score.parts)

    for i in range(0, len(parts), 2):
        if i + 1 < len(parts):
            p1 = parts[i]
            p2 = parts[i + 1]

            new_part = stream.Part()
            for el in p1.getElementsByClass(
                ["TimeSignature", "KeySignature", "Clef", "Instrument"]
            ):
                new_part.insert(0.0, copy.deepcopy(el))

            v1 = stream.Voice()
            v2 = stream.Voice()

            for el in p1.flatten().notesAndRests:
                v1.insert(el.offset, copy.deepcopy(el))
            for el in p2.flatten().notesAndRests:
                v2.insert(el.offset, copy.deepcopy(el))

            new_part.insert(0.0, v1)
            new_part.insert(0.0, v2)
            condensed_score.insert(0.0, new_part)
        else:
            condensed_score.insert(0.0, copy.deepcopy(parts[i]))

    return condensed_score


def clean_score(score: stream.Score) -> stream.Score:
    """
    Clean up rests in a score: remove rests that collide with notes and merge adjacent rests.

    Parameters
    ----------
    score : stream.Score
        Score to clean.

    Returns
    -------
    stream.Score
        Cleaned score.
    """
    cleaned_score = copy.deepcopy(score)
    all_notes = list(cleaned_score.flatten().notes)

    parts_to_remove = []

    for part in cleaned_score.parts:
        part_notes = list(part.flatten().notes)
        if not part_notes:
            parts_to_remove.append(part)
            continue

        rests_to_remove = []
        for r in part.getElementsByClass("Rest"):
            r_start = r.offset
            r_end = r_start + r.quarterLength

            overlaps_with_note = False
            for n in all_notes:
                if (
                    max(r_start, n.offset)
                    < min(r_end, n.offset + n.quarterLength) - 0.001
                ):
                    overlaps_with_note = True
                    break

            if overlaps_with_note:
                rests_to_remove.append(r)

        for r in rests_to_remove:
            try:
                part.remove(r)
            except Exception:
                pass

    for part in parts_to_remove:
        cleaned_score.remove(part)

    for part in cleaned_score.parts:
        while True:
            merged_any = False
            rests = sorted(
                list(part.getElementsByClass("Rest")), key=lambda r: r.offset
            )
            for i in range(len(rests) - 1):
                r1 = rests[i]
                r2 = rests[i + 1]
                if abs(r2.offset - (r1.offset + r1.quarterLength)) < 0.001:
                    part.remove(r1)
                    part.remove(r2)
                    new_rest = note.Rest(
                        quarterLength=r1.quarterLength + r2.quarterLength
                    )
                    part.insert(r1.offset, new_rest)
                    merged_any = True
                    break
            if not merged_any:
                break

    return cleaned_score


def append_score(base_score: stream.Score, next_score: stream.Score) -> stream.Score:
    """
    Append next_score sequentially onto the end of base_score.

    Parameters
    ----------
    base_score : stream.Score
        Initial score section.
    next_score : stream.Score
        Subsequent score section to concatenate.

    Returns
    -------
    stream.Score
        Combined sequential score.
    """
    shift = base_score.highestTime
    for i in range(min(len(base_score.parts), len(next_score.parts))):
        p_base = base_score.parts[i]
        p_next = next_score.parts[i]
        for el in p_next.flatten().notesAndRests:
            p_base.insert(shift + el.offset, copy.deepcopy(el))
    return base_score
