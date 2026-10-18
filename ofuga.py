#!/usr/bin/env python3
"""
ofuga.py
========
Algorithmic Baroque Fugue Generator using Hill Climbing Heuristic Search.

This engine synthesizes multi-voice Baroque counterpoint following classical
fugue composition rules:
1. Dux (Subject) entry and exposition.
2. Comes (Tonal Answer) with interval-adjusted transposition to the dominant.
3. Melodic transformations: Inversion (mirror), Retrograde (cancrizans), and Tempo Scaling (augmentation/diminution).
4. Heuristic optimization (Hill Climbing) over voice entry offsets (p) and transformations.
5. Fitness function balancing vertical harmonic consonance, voice independence, and density.
6. Post-processing: rest condensation and grand-staff organ voice reduction.
"""

import argparse
import copy
import os
import random
import sys
from typing import List, Optional, Tuple

from music21 import instrument, note, stream

from music_lib import (
    _find_musescore_binary,
    add_voice_to_score,
    append_score,
    clean_score,
    combine_parts_to_voices,
    read,
    set_voice,
)


def get_answer(theme: stream.Stream) -> stream.Stream:
    """
    Generate the fugue answer (*comes*) transposed to the dominant with tonal adjustments.

    In Baroque fugues, the answer enters a 5th above (or 4th below). To preserve
    tonal stability, early ascending or descending intervals are adjusted.

    Parameters
    ----------
    theme : stream.Stream
        Input melodic subject (dux).

    Returns
    -------
    stream.Stream
        Transposed and tonally adjusted answer stream.
    """
    theme_flat = theme.flatten()
    notes = [n for n in theme_flat.notes if n.isNote]
    if not notes:
        return copy.deepcopy(theme)

    rhythm = [n.quarterLength for n in notes]
    midi_values = [n.pitch.midi for n in notes]

    start_pitch = midi_values[0]
    intervals = [
        midi_values[i] - midi_values[i - 1] for i in range(1, len(midi_values))
    ]

    transposition = random.choice([7, -5])
    start_transposed = start_pitch + transposition

    # Tonal mutation on initial intervals
    k = max(1, random.randint(1, max(1, len(intervals) // 4)))
    for i in range(min(k, len(intervals))):
        if intervals[i] > 0:
            intervals[i] -= 2
        else:
            intervals[i] += 2

    answer_midi = [start_transposed]
    for interval_val in intervals:
        answer_midi.append(answer_midi[-1] + interval_val)

    answer_stream = stream.Stream()
    for midi_val, q_len in zip(answer_midi, rhythm):
        new_note = note.Note(midi_val)
        new_note.quarterLength = q_len
        answer_stream.append(new_note)

    return answer_stream


def is_tonic_or_dominant(pitch_class: int, key_sig) -> bool:
    """Check if the given pitch class corresponds to scale degree 1 (tonic) or 5 (dominant)."""
    if key_sig is None:
        return True
    try:
        tonic = key_sig.pitchFromDegree(1).pitchClass
        dominant = key_sig.pitchFromDegree(5).pitchClass
        return pitch_class in (tonic, dominant)
    except Exception:
        return True


def judge_my_theme(theme: stream.Stream, verbose: bool = True) -> bool:
    """
    Validate whether an input theme satisfies classical Baroque fugue subject constraints.

    Checks:
    - Subject begins on tonic or dominant degree.
    - Meter is 4/4.
    - Measure length is between 2.0 and 5.0 measures (8 to 20 quarter notes).
    - Melodic compass does not exceed one octave (<= 12 semitones).

    Parameters
    ----------
    theme : stream.Stream
        Input theme to validate.
    verbose : bool
        Whether to print diagnostic messages if validation fails.

    Returns
    -------
    bool
        True if theme satisfies all fugal rules, False otherwise.
    """
    theme_flat = theme.flatten()
    notes = [n for n in theme_flat.notes if n.isNote]
    if not notes:
        if verbose:
            print("[Validation] Error: Theme contains no notes.")
        return False

    try:
        key_sig = theme_flat.analyze("key")
    except Exception:
        key_sig = None

    if key_sig and not is_tonic_or_dominant(notes[0].pitch.pitchClass, key_sig):
        if verbose:
            print(
                f"[Validation] Rejected: First note ({notes[0].nameWithOctave}) "
                f"is neither tonic nor dominant in {key_sig}."
            )
        return False

    time_signatures = theme_flat.getElementsByClass("TimeSignature")
    current_meter = time_signatures[0].ratioString if time_signatures else "4/4"
    if current_meter != "4/4":
        if verbose:
            print(f"[Validation] Rejected: Meter is {current_meter}, expected 4/4.")
        return False

    num_measures = theme_flat.highestTime / 4.0
    if not (2.0 <= num_measures <= 5.0):
        if verbose:
            print(
                f"[Validation] Rejected: Theme duration is {num_measures:.2f} measures "
                f"(expected 2.0 to 5.0 measures)."
            )
        return False

    midi_pitches = [n.pitch.midi for n in notes]
    pitch_span = max(midi_pitches) - min(midi_pitches)
    if pitch_span > 12:
        if verbose:
            print(
                f"[Validation] Rejected: Pitch span ({pitch_span} semitones) "
                f"exceeds an octave (12 semitones)."
            )
        return False

    return True


def transpose(theme: stream.Stream, interval_val: int = 7) -> stream.Stream:
    """Transpose a theme by a given semitone interval."""
    return theme.transpose(interval_val)


def inverse(theme: stream.Stream) -> stream.Stream:
    """
    Produce the melodic inversion (mirror counterpoint) of a theme.

    Ascending intervals become descending intervals of the same magnitude, and vice-versa.
    """
    theme_flat = theme.flatten()
    notes = [n for n in theme_flat.notes if n.isNote]
    if not notes:
        return copy.deepcopy(theme)

    rhythm = [n.quarterLength for n in notes]
    midi_values = [n.pitch.midi for n in notes]

    start_pitch = midi_values[0]
    intervals = [
        midi_values[i] - midi_values[i - 1] for i in range(1, len(midi_values))
    ]

    inversed_midi = [start_pitch]
    for interval_val in intervals:
        inversed_midi.append(inversed_midi[-1] - interval_val)

    inversed_stream = stream.Stream()
    for midi_val, q_len in zip(inversed_midi, rhythm):
        new_note = note.Note(midi_val)
        new_note.quarterLength = q_len
        inversed_stream.append(new_note)

    return inversed_stream


def retrograde(theme: stream.Stream) -> stream.Stream:
    """
    Produce the retrograde (cancrizans / crab canon) of a theme.

    Reverses the sequence of notes while preserving original metric positions.
    """
    if isinstance(theme, stream.Score):
        new_score = stream.Score()
        for part in theme.parts:
            new_score.insert(0.0, retrograde(part))
        return new_score

    theme_flat = theme.flatten()
    notes_and_rests = list(theme_flat.notesAndRests)
    reversed_elements = list(reversed(notes_and_rests))

    new_stream = theme.__class__()
    for el in theme_flat.getElementsByClass(
        ["TimeSignature", "KeySignature", "Clef", "Instrument"]
    ):
        new_stream.insert(0.0, copy.deepcopy(el))

    for orig_el, rev_el in zip(notes_and_rests, reversed_elements):
        new_el = copy.deepcopy(rev_el)
        new_el.quarterLength = orig_el.quarterLength
        new_stream.append(new_el)

    return new_stream


def change_tempo(theme: stream.Stream, factor: float = 1.0) -> stream.Stream:
    """
    Perform rhythmic augmentation (factor > 1.0) or diminution (factor < 1.0).
    """
    if factor == 1.0:
        return copy.deepcopy(theme)

    if isinstance(theme, stream.Score):
        new_score = stream.Score()
        for part in theme.parts:
            new_score.insert(0.0, change_tempo(part, factor))
        return new_score

    new_stream = theme.__class__()
    for el in theme.getElementsByClass(
        ["TimeSignature", "KeySignature", "Clef", "Instrument"]
    ):
        new_stream.insert(0.0, copy.deepcopy(el))

    for el in theme.flatten().notesAndRests:
        new_el = copy.deepcopy(el)
        new_el.quarterLength *= factor
        new_stream.append(new_el)

    return new_stream


def create_harmony(theme: stream.Stream, degree_shift: int = -2) -> stream.Stream:
    """
    Generate a diatonic counter-melody shifted by scale degrees within the key.
    """
    harmony = theme.__class__()
    theme_flat = theme.flatten()
    try:
        key_sig = theme_flat.analyze("key")
    except Exception:
        return theme

    for el in theme_flat.getElementsByClass(
        ["TimeSignature", "KeySignature", "Clef", "Instrument"]
    ):
        harmony.insert(0.0, copy.deepcopy(el))

    for el in theme_flat.notesAndRests:
        if el.isNote:
            deg_info = key_sig.getScaleDegreeAndAccidentalFromPitch(el.pitch)
            if deg_info and deg_info[0] is not None:
                deg = deg_info[0]
                new_deg = (deg + degree_shift - 1) % 7 + 1
                oct_shift = (deg + degree_shift - 1) // 7

                new_pitch = key_sig.pitchFromDegree(new_deg)
                new_pitch.octave = el.pitch.octave + oct_shift

                harmony.append(
                    note.Note(new_pitch, quarterLength=el.quarterLength)
                )
            else:
                harmony.append(copy.deepcopy(el))
        else:
            harmony.append(copy.deepcopy(el))

    return harmony


def apply_random_transformations(
    theme: stream.Stream,
) -> Tuple[stream.Stream, str]:
    """
    Apply a stochastic contrapuntal transformation to generate candidate voices.

    Transformations: answer, transpose, harmony, retrograde, inverse, or identity.
    Followed by optional rhythmic augmentation (2.0) or diminution (0.5).
    """
    transformed = copy.deepcopy(theme)
    method = random.choice(
        ["answer", "transpose", "inverse", "harmony", "retrograde", "nothing"]
    )

    if method == "answer":
        transformed = get_answer(transformed)
    elif method == "transpose":
        interval_val = random.choice([-12, -7, -5, -2, 2, 5, 7, 12])
        transformed = transpose(transformed, interval_val)
    elif method == "harmony":
        shift = random.choice([-5, -4, -3, -2, 2, 3, 4, 5])
        transformed = create_harmony(transformed, degree_shift=shift)
    elif method == "retrograde":
        transformed = retrograde(transformed)
    elif method == "inverse":
        transformed = inverse(transformed)

    tempo_factor = random.choice([0.5, 1.0, 2.0])
    transformed = change_tempo(transformed, factor=tempo_factor)
    return transformed, f"{method}_tempo_{tempo_factor}"


def find_difference(score1: stream.Stream, score2: stream.Stream) -> float:
    """
    Calculate melodic divergence between two voices (pitch intervals and rhythmic contours).

    Returns 1.0 for completely distinct voices, 0.0 for identical or parallel voices.
    """
    notes1 = list(score1.flatten().notes)
    notes2 = list(score2.flatten().notes)

    if not notes1 or not notes2:
        return 1.0

    p1 = [n.pitch.midi if n.isNote else n.pitches[0].midi for n in notes1]
    p2 = [n.pitch.midi if n.isNote else n.pitches[0].midi for n in notes2]

    d1 = [n.quarterLength for n in notes1]
    d2 = [n.quarterLength for n in notes2]

    if len(p1) != len(p2):
        return 1.0

    if p1 == p2 or d1 == d2:
        return 0.0

    if len(p1) > 1 and len(p2) > 1:
        intervals1 = [p1[i] - p1[i - 1] for i in range(1, len(p1))]
        intervals2 = [p2[i] - p2[i - 1] for i in range(1, len(p2))]
        if intervals1 == intervals2 and d1 == d2:
            return 0.0

    return 1.0


def evaluate_density(score: stream.Score) -> float:
    """Calculate the aggregate rhythmic density of notes in a score."""
    notes = list(score.flatten().notes)
    density_val = 0.0
    for n in notes:
        q_len = max(n.quarterLength, 0.125)
        density_val += 1.0 / q_len
    return density_val


def evaluate(score: stream.Score) -> float:
    """
    Heuristic fitness function evaluating the contrapuntal quality of a polyphonic score.

    Scoring components:
    - Vertical harmonic consonance:
      + Major / Minor thirds and sixths (m in [3, 4, 8, 9]): +15 * duration
      + Perfect consonances (fifths, octaves): +5 * duration
      + Dissonances (unisons, 2nds, 7ths, tritones): -100 * duration
    - Polyphonic density bonus: (active_voices^2) * duration * 20
    - Voice independence bonus: avg_divergence * 500
    """
    parts = list(score.parts)
    if len(parts) < 2:
        return 0.0

    score_fitness = 0.0
    chordified_score = score.chordify()

    for c in chordified_score.recurse().getElementsByClass("Chord"):
        unique_pitches = list({p.pitchClass for p in c.pitches})
        num_voices_active = len(unique_pitches)
        duration = c.quarterLength

        if num_voices_active < 2:
            continue

        score_fitness += (num_voices_active**2) * duration * 20

        for i in range(len(c.pitches)):
            for j in range(i + 1, len(c.pitches)):
                p1 = c.pitches[i]
                p2 = c.pitches[j]

                diff = abs(p1.midi - p2.midi)
                m = diff % 12

                if m in [3, 4, 8, 9]:
                    score_fitness += 15 * duration
                elif diff > 0 and m == 0:
                    score_fitness += 5 * duration
                elif m in [5, 7]:
                    score_fitness += 5 * duration
                elif diff == 0 or m in [1, 2, 6, 10, 11]:
                    score_fitness -= 100 * duration

    total_diff = 0.0
    count = 0
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            total_diff += find_difference(parts[i], parts[j])
            count += 1
    avg_diff = total_diff / count if count > 0 else 0.0

    return score_fitness + (avg_diff * 500)


def find_best_p(
    existing_score: stream.Score, candidate: stream.Stream
) -> Tuple[Optional[stream.Score], float]:
    """
    Find the optimal temporal entry offset (p) for a candidate voice via exhaustive search.

    Tests entry points from beat 0 up to highestTime // 2.
    """
    min_p = 0
    best_score = -1e9
    best_individual = None

    max_p = max(0, int(existing_score.highestTime / 2))
    for p in range(min_p, max_p + 1):
        individual = add_voice_to_score(existing_score, candidate, p)
        score_val = evaluate(individual)
        if score_val > best_score:
            best_score = score_val
            best_individual = individual

    return best_individual, best_score


def run_hill_climbing(
    base_theme: stream.Stream,
    num_voices: int = 4,
    n_iterations: int = 8,
    verbose: bool = True,
) -> stream.Score:
    """
    Synthesize polyphony by incrementally adding voices using Hill Climbing search.

    Parameters
    ----------
    base_theme : stream.Stream
        Seed theme for this section.
    num_voices : int
        Target number of voices to accumulate.
    n_iterations : int
        Number of candidate transformations evaluated per voice layer.
    verbose : bool
        Whether to print generation progress.

    Returns
    -------
    stream.Score
        Generated polyphonic score section.
    """
    current_score = stream.Score()
    current_score.insert(0.0, set_voice(base_theme, 0.0))

    thematic_pool = [
        base_theme,
        get_answer(base_theme),
        retrograde(base_theme),
        inverse(base_theme),
    ]

    for voice_idx in range(2, num_voices + 1):
        if verbose:
            print(f"    Voice {voice_idx}/{num_voices}...", end="", flush=True)

        best_candidate_score = -1e9
        best_individual = None

        for _ in range(n_iterations):
            chosen_base = random.choice(thematic_pool)
            new_voice_cand, _ = apply_random_transformations(chosen_base)
            individual, score_val = find_best_p(current_score, new_voice_cand)
            if score_val > best_candidate_score:
                best_candidate_score = score_val
                best_individual = individual

        if best_individual is not None:
            current_score = best_individual

        if verbose:
            print(f" fitness = {best_candidate_score:.2f}")

    return current_score


def generate_fugue(
    input_file: str,
    output_path: str = "fugue.musicxml",
    num_voices: int = 4,
    iterations: int = 8,
    export_formats: Optional[List[str]] = None,
    verbose: bool = True,
) -> stream.Score:
    """
    Generate a full three-section Baroque fugue from an input subject score.

    Structure:
    1. Exposition: Polyphonic development of the main subject (Dux).
    2. Middle Section: Tonal answer (Comes) development.
    3. Stretto / Final Section: Retrograde and inverted transformations.
    4. Coda: Final tonic pedal point resolution.

    Parameters
    ----------
    input_file : str
        Path to input theme score (.mscz, .musicxml, .mid).
    output_path : str
        Destination path for generated score.
    num_voices : int
        Number of polyphonic voices (default: 4).
    iterations : int
        Candidate evaluations per voice in Hill Climbing (default: 8).
    export_formats : Optional[List[str]]
        Additional formats to export (e.g. ['mid', 'mp3', 'pdf']).
    verbose : bool
        Whether to print progress messages.

    Returns
    -------
    stream.Score
        Final combined and condensed fugue score.
    """
    if verbose:
        print(f"Loading input theme from '{input_file}'...")
    raw_score = read(input_file)
    theme = raw_score.parts[0]
    organs = instrument.PipeOrgan()
    theme.insert(0.0, organs)

    if not judge_my_theme(theme, verbose=verbose):
        print("[Warning] Theme does not strictly meet all classical criteria, proceeding anyway...")

    if verbose:
        print("\n=== Section 1: Main Subject (Dux) Exposition ===")
    s1 = run_hill_climbing(
        theme, num_voices=num_voices, n_iterations=iterations, verbose=verbose
    )

    if verbose:
        print("\n=== Section 2: Tonal Answer (Comes) Development ===")
    answer_theme = get_answer(theme)
    s2 = run_hill_climbing(
        answer_theme,
        num_voices=num_voices,
        n_iterations=iterations,
        verbose=verbose,
    )

    if verbose:
        print("\n=== Section 3: Retrograde & Mirror Section ===")
    retrograde_theme = retrograde(theme)
    s3 = run_hill_climbing(
        retrograde_theme,
        num_voices=num_voices,
        n_iterations=iterations,
        verbose=verbose,
    )

    # Concatenate the three fugal sections
    final_score = copy.deepcopy(s1)
    final_score = append_score(final_score, s2)
    final_score = append_score(final_score, s3)

    # Add concluding tonic pedal note in bass
    first_note = None
    for n in theme.flatten().notes:
        if n.isNote:
            first_note = n
            break

    if first_note is not None and len(final_score.parts) > 0:
        end_time = final_score.highestTime
        final_cadence_note = note.Note(first_note.pitch, quarterLength=4.0)
        final_score.parts[0].insert(end_time, final_cadence_note)

    # Clean rests and condense parts into 2-voice keyboard staves
    cleaned_score = clean_score(final_score)
    combined_score = combine_parts_to_voices(cleaned_score)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    combined_score.write("musicxml", fp=output_path)
    if verbose:
        total_notes = len([n for n in final_score.flatten().notes if n.isNote])
        print(f"\n[Success] Fugue successfully exported to: {output_path}")
        print(f"Total notes generated: {total_notes}")

    # Handle optional format exports
    if export_formats:
        base_name, _ = os.path.splitext(output_path)
        musescore_bin = _find_musescore_binary()

        for fmt in export_formats:
            target_ext = fmt.lower().lstrip(".")
            target_file = f"{base_name}.{target_ext}"

            if target_ext in ["mid", "midi"]:
                combined_score.write("midi", fp=target_file)
                if verbose:
                    print(f"[Export] MIDI written to: {target_file}")
            elif target_ext in ["mp3", "pdf", "wav"]:
                if musescore_bin:
                    try:
                        import subprocess

                        subprocess.run(
                            [musescore_bin, output_path, "-o", target_file],
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        if verbose:
                            print(
                                f"[Export] {target_ext.upper()} written to: {target_file}"
                            )
                    except Exception as err:
                        print(
                            f"[Export Error] Failed to export {target_ext}: {err}"
                        )
                else:
                    print(
                        f"[Export Warning] MuseScore not found, skipping {target_ext} export."
                    )

    return combined_score


def main():
    parser = argparse.ArgumentParser(
        description="Baroque Fugue Generator: Synthesize polyphonic counterpoint using Hill Climbing search."
    )
    # Default to sample theme if available
    default_input = "examples/fly_me_to_the_moon.musicxml"
    if not os.path.exists(default_input):
        for candidate in [
            "examples/fly_me_to_the_moon.mscz",
            "examples/bach_art_of_fugue.musicxml",
            "z.mscz",
        ]:
            if os.path.exists(candidate):
                default_input = candidate
                break

    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=default_input,
        help="Input theme file (.musicxml, .mscz, or .mid).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="output/fugue.musicxml",
        help="Output MusicXML file path (default: output/fugue.musicxml).",
    )
    parser.add_argument(
        "-v",
        "--voices",
        type=int,
        default=4,
        help="Number of polyphonic voices per section (default: 4).",
    )
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=8,
        help="Number of candidates evaluated per voice in Hill Climbing (default: 8).",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible generation.",
    )
    parser.add_argument(
        "--export-midi",
        action="store_true",
        help="Also export a .mid MIDI audio file.",
    )
    parser.add_argument(
        "--export-mp3",
        action="store_true",
        help="Also export an .mp3 audio file (requires MuseScore).",
    )
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="Also export a .pdf sheet music score (requires MuseScore).",
    )

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    export_formats = []
    if args.export_midi:
        export_formats.append("mid")
    if args.export_mp3:
        export_formats.append("mp3")
    if args.export_pdf:
        export_formats.append("pdf")

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        sys.exit(1)

    generate_fugue(
        input_file=args.input,
        output_path=args.output,
        num_voices=args.voices,
        iterations=args.iterations,
        export_formats=export_formats,
        verbose=True,
    )


if __name__ == "__main__":
    main()
