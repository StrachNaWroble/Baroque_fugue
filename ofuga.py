from music21 import *
import random
import copy
from music_lib import *

def get_answer(theme):
    theme = theme.flatten()
    notes = [n for n in theme.notes if n.isNote]
    rythm = [n.quarterLength for n in notes]
    midi_values = [n.pitch.midi for n in notes]

    s = midi_values[0]
    a_intervals = []
    for i in range(1, len(midi_values)):
        a_intervals.append(midi_values[i] - midi_values[i-1])

    transp = random.choice([7, -5])
    s_t = s + transp

    k = random.randint(1, int(len(a_intervals)/4))
    
    for i in range(k):
        if a_intervals[i] > 0: a_intervals[i] -= 2 
        else: a_intervals[i] += 2

    answer_midi = [s_t]
    
    for i in range(len(a_intervals)):
        answer_midi.append(answer_midi[-1] + a_intervals[i])

    answer_stream = stream.Stream()
        
    for midi_val, q_len in zip(answer_midi, rythm):
        new_note = note.Note(midi_val)
        new_note.quarterLength = q_len
        answer_stream.append(new_note)

    return answer_stream

def is_tonic_or_dominant(note, key_sig):
    tonic = key_sig.pitchFromDegree(1).pitchClass
    dominant = key_sig.pitchFromDegree(5).pitchClass
    return (note == tonic or note == dominant)

def judge_my_theme(theme):
    theme = theme.flatten()
    notes = theme.notes

    key_sig = theme.analyze('key')
    key_pitches = [p.pitchClass for p in key_sig.pitches]
    
    if not all(n.pitch.pitchClass in key_pitches for n in notes if n.isNote):  #wszytskie dźwięki należą do tonacji
        print("nie wszytskie dźwięki należą do tonacji")
        #return False

    if not is_tonic_or_dominant(notes[0].pitch.pitchClass, key_sig): #pierwszy dźwięk to tonika lub dominanta
        print("pierwszy dźwięk to nie jest tonika ani dominanta")
        return False

    time_signatures = theme.getElementsByClass('TimeSignature') 
    current_meter = time_signatures[0].ratioString if time_signatures else '4/4' #metrum = 4/4
    if not current_meter == '4/4':
        print("matrum to nie 4/4")
        return False

    num_measures = theme.highestTime / 4.0 
    if not 2.0 <= num_measures <= 5.0: #ma od 2 do 5 taktów
        print("temat nie ma od 2 do 5 taktów")
        return False
    
    values = [n.pitch.midi for n in notes]
    if (max(values) - min(values)) > 12: #dzwięki nie różnią się o więcej niż oktawę
        print("dzwieki różnią się o więcej niż oktawę")
        return False

    return True

def transpose(theme, interval=7):
    return theme.transpose(interval)

def inverse(theme):
    theme = theme.flatten()
    notes = [n for n in theme.notes if n.isNote]
    rythm = [n.quarterLength for n in notes]
    midi_values = [n.pitch.midi for n in notes]

    s = midi_values[0]
    a_intervals = []
    for i in range(1, len(midi_values)):
        a_intervals.append(midi_values[i] - midi_values[i-1])
    
    inversed = [s]
    
    for i in range(len(a_intervals)):
        inversed.append(inversed[-1] - a_intervals[i])

    inversed_stream = stream.Stream()
        
    for midi_val, q_len in zip(inversed, rythm):
        new_note = note.Note(midi_val)
        new_note.quarterLength = q_len
        inversed_stream.append(new_note)

    return inversed_stream

def retrograde(theme):
    if isinstance(theme, stream.Score):
        new_score = stream.Score()
        for part in theme.parts:
            new_score.insert(0.0, retrograde(part))
        return new_score

    theme_flat = theme.flatten()
    notes = [n for n in theme_flat.notesAndRests]
    reversed_notes = list(reversed(notes))
    
    new_stream = theme.__class__()
    for el in theme_flat.getElementsByClass(['TimeSignature', 'KeySignature', 'Clef', 'Instrument']):
        new_stream.insert(0.0, copy.deepcopy(el))
        
    for orig_el, rev_el in zip(notes, reversed_notes):
        new_el = copy.deepcopy(rev_el)
        new_el.quarterLength = orig_el.quarterLength
        new_stream.append(new_el)
    return new_stream

def change_tempo(theme, factor=1.0):
    if factor == 1.0:
        return copy.deepcopy(theme)

    if isinstance(theme, stream.Score):
        new_score = stream.Score()
        for part in theme.parts:
            new_score.insert(0.0, change_tempo(part, factor))
        return new_score

    new_stream = theme.__class__()
    for el in theme.getElementsByClass(['TimeSignature', 'KeySignature', 'Clef', 'Instrument']):
        new_stream.insert(0.0, copy.deepcopy(el))
        
    for el in theme.flatten().notesAndRests:
        new_el = copy.deepcopy(el)
        new_el.quarterLength *= factor
        new_stream.append(new_el)
        
    return new_stream

def create_harmony(theme, degree_shift=-2):
    harmony = theme.__class__()
    theme_flat = theme.flatten()
    try:
        key_sig = theme_flat.analyze('key')
    except:
        return theme
    
    for el in theme_flat.getElementsByClass(['TimeSignature', 'KeySignature', 'Clef', 'Instrument']):
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
                
                harmony.append(note.Note(new_pitch, quarterLength=el.quarterLength))
            else:
                harmony.append(copy.deepcopy(el))
        else:
            harmony.append(copy.deepcopy(el))
            
    return harmony

def apply_random_transformations(theme):
    transformed = copy.deepcopy(theme)

    method = random.choice(["answer", "transpose", "inverse", "harmony", "retrograde", "nothing"])
    if method == "answer":
        transformed = get_answer(transformed)
    elif method == "transpose":
        interval = random.choice([-12, -7, -5, -2, 2, 5, 7, 12])
        transformed = transpose(transformed, interval) 
    elif method == "harmony":
        shift = random.choice([-5, -4, -3, -2, 2, 3, 4, 5])
        transformed = create_harmony(transformed, degree_shift=shift)
    elif method == "retrograde":
        transformed = retrograde(transformed)
    elif method == "inverse":
        transformed = inverse(transformed)
    else:
        pass
    
    tempo_factor = random.choice([0.5, 1.0, 2.0])
    transformed = change_tempo(transformed, factor=tempo_factor)
    return transformed, f"{method}_tempo_{tempo_factor}"

def find_best_p(existing_score, candidate):
    min_p = 0
    best_p = 0
    best_score = -1e9
    best_osobnik = None
    
    max_p = int(existing_score.highestTime / 2)
    for p in range(min_p, max_p + 1):
        osobnik = add_voice_to_score(existing_score, candidate, p)
        score = evaluate(osobnik)
        if score > best_score:
            best_score = score
            best_p = p
            best_osobnik = osobnik
    return best_osobnik, best_score

def find_difference(score1, score2):
    notes1 = list(score1.flatten().notes)
    notes2 = list(score2.flatten().notes)
    
    if not notes1 or not notes2:
        return 1.0
        
    p1 = [n.pitch.midi if n.isNote else n.pitches[0].midi for n in notes1]
    p2 = [n.pitch.midi if n.isNote else n.pitches[0].midi for n in notes2]
    
    d1 = [n.quarterLength for n in notes1]
    d2 = [n.quarterLength for n in notes2]
    
    offset1 = notes1[0].offset if notes1 else 0.0
    offset2 = notes2[0].offset if notes2 else 0.0
    
    if len(p1) != len(p2):
        return 1.0
        
    if p1 == p2 or d1 == d2:
        return 0.0
        
    if len(p1) > 1 and len(p2) > 1:
        intervals1 = [p1[i] - p1[i-1] for i in range(1, len(p1))]
        intervals2 = [p2[i] - p2[i-1] for i in range(1, len(p2))]
        if intervals1 == intervals2 and d1 == d2:
            return 0.0
            
    return 1.0

def evaluate_density(score):
    notes = list(score.flatten().notes)
    density_val = 0.0
    for n in notes:
        q_len = max(n.quarterLength, 0.125)
        density_val += 1.0 / q_len
    return density_val

def evaluate(score):
    parts = list(score.parts)
    if len(parts) < 2:
        return 0.0

    score_fitness = 0.0
    chordified_score = score.chordify()
    
    for c in chordified_score.recurse().getElementsByClass('Chord'):
        unique_pitches = list([p.pitchClass for p in c.pitches])
        num_voices_active = len(unique_pitches)
        duration = c.quarterLength
        
        if num_voices_active < 2:
            continue
            
        score_fitness += (num_voices_active ** 2) * duration * 20
        
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
    
    return score_fitness + (avg_diff) * 500

def run_hill_climbing(base_theme, num_voices=5, n=8):
    
    current_score = stream.Score()
    current_score.insert(0.0, set_voice(base_theme, 0.0))
    
    themes = [
        base_theme,
        get_answer(base_theme),
        retrograde(base_theme),
        inverse(base_theme)
    ]
    
    for voice_idx in range(2, num_voices + 1):
        print(f"    głos: {voice_idx}/{num_voices} ......... ")
        best_candidate_score = -1e9
        best_osobnik = None
        
        for i in range(n):
            chosen_base = random.choice(themes)
            new_voice_cand, method = apply_random_transformations(chosen_base)
            osobnik, score_val = find_best_p(current_score, new_voice_cand)
            if score_val > best_candidate_score:
                best_candidate_score = score_val
                best_osobnik = osobnik
                
        current_score = best_osobnik
        print(f"        wynik heurystyki = {best_candidate_score:.2f}")
            
    return current_score

def main():
    theme = read("z.mscz").parts[0]
    organs = instrument.PipeOrgan()
    theme.insert(0.0, organs)
    if not judge_my_theme(theme):
        print("Podany temat nie spełnia wymagań :(")
        return

    num_voices = 8
    
    print("\n--- Główny temat ---")
    s1 = run_hill_climbing(theme, num_voices)
    
    print("\n--- Odpoweidź do tematu ---")
    answer_theme = get_answer(theme)
    s2 = run_hill_climbing(answer_theme, num_voices)
    
    print("\n--- Retrogradacja tematu ---")
    retrograde_theme = retrograde(theme)
    s3 = run_hill_climbing(retrograde_theme, num_voices)
    
    s_final = copy.deepcopy(s1)
    s_final = append_score(s_final, s2)
    s_final = append_score(s_final, s3)
    
    first_note = None
    for n in theme.flatten().notes:
        if n.isNote:
            first_note = n
            break
            
    if first_note is not None:
        end_time = s_final.highestTime
        final_note = note.Note(first_note.pitch, quarterLength=4.0)
        s_final.parts[0].insert(end_time, final_note)
    
    s_cleaned = clean_score(s_final) 
    s_combined = combine_parts_to_voices(s_cleaned)
    
    nazwa_pliku = "flymetothemoon.musicxml"
    s_combined.write('musicxml', fp=nazwa_pliku)
    print(f"\nRezultat: {nazwa_pliku}")
    
    print(f"liczba nut: {len([n for n in s_final.flatten().notes if n.isNote])}")

if __name__ == '__main__':
    main()
