import torch
import numpy as np
import os
import folder_paths
import math
from .audio_nodes import AudioNodeBase
from ...tooltips import apply_tooltips
from server import PromptServer
from aiohttp import web
import shutil

@apply_tooltips
class MIDIToAudio(AudioNodeBase):
    """Converts MIDI data to audio format compatible with ComfyUI's audio system."""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "midi": ("MIDI",),
                "instrument_type": (["Piano", "Synth", "Bass", "Drums"],),
                "sample_rate": ("INT", {
                    "default": 44100,
                    "min": 8000,
                    "max": 192000,
                    "step": 1
                }),
                "volume": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01
                })
            }
        }
    
    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "convert_midi_to_audio"
    CATEGORY = "RyanOnTheInside/Audio/MIDI"
    DESCRIPTION = "This will produce rudimentary approximations of MIDI notes for quick reference and nothing more. May or may not get the notes right, especially for drums."
    
    def generate_instrument_waveform(self, frequency, t, instrument_type, envelope, note_number=60):
        """Generate waveform based on the selected instrument type"""
        if instrument_type == "Piano":
            # Piano-like sound with some harmonics
            waveform = 0.5 * np.sin(2 * np.pi * frequency * t)  # Fundamental
            waveform += 0.2 * np.sin(2 * np.pi * frequency * 2 * t)  # 1st harmonic (octave)
            waveform += 0.1 * np.sin(2 * np.pi * frequency * 3 * t)  # 2nd harmonic
            waveform += 0.05 * np.sin(2 * np.pi * frequency * 4 * t)  # 3rd harmonic
            # Add faster decay for piano-like sound
            decay = np.exp(-t * 3)
            return waveform * envelope * decay
        
        elif instrument_type == "Bass":
            # Bass with more low frequencies
            waveform = 0.6 * np.sin(2 * np.pi * frequency * t)  # Fundamental
            waveform += 0.3 * np.sin(2 * np.pi * frequency * 2 * t)  # 1st harmonic
            # Add some distortion for bass character
            waveform = np.tanh(waveform * 1.5) * 0.7
            # Slower decay for bass
            decay = np.exp(-t * 2)
            return waveform * envelope * decay
        
        elif instrument_type == "Drums":
            # Use standard MIDI drum mappings (channel 10)
            # Define custom synthesis for each drum sound based on note number
            
            # Bass/Kick Drums
            if note_number in [35, 36]:  # Bass Drum 2, Bass Drum 1
                # Low frequency sine with very fast decay
                waveform = np.sin(2 * np.pi * 60 * t)  # Fixed low frequency for kick
                waveform += 0.2 * np.sin(2 * np.pi * 90 * t)  # Add some mid tone
                decay = np.exp(-t * 20)  # Very quick decay
                return waveform * envelope * decay
            
            # Snare Drums
            elif note_number in [38, 40]:  # Acoustic Snare, Electric Snare
                # Mix of sine wave and noise
                waveform = 0.3 * np.sin(2 * np.pi * 150 * t)  # Mid frequency tone
                noise = np.random.rand(len(t)) * 2 - 1  # White noise
                decay = np.exp(-t * 15)  # Fast decay
                return (waveform + 0.7 * noise) * envelope * decay
            
            # Hi-Hats
            elif note_number in [42, 44, 46]:  # Closed, Pedal, Open Hi-Hats
                # Mostly noise with different decay times
                noise = np.random.rand(len(t)) * 2 - 1
                # Different decay times based on hi-hat type
                if note_number == 42:  # Closed Hi-Hat
                    decay = np.exp(-t * 30)  # Very short
                elif note_number == 44:  # Pedal Hi-Hat
                    decay = np.exp(-t * 25)  # Short
                else:  # Open Hi-Hat
                    decay = np.exp(-t * 10)  # Longer
                
                # Add some high frequency sine for metallic character
                waveform = noise + 0.1 * np.sin(2 * np.pi * 800 * t)
                
                return waveform * envelope * decay
            
            # Toms
            elif note_number in [41, 43, 45, 47, 48, 50]:  # Various Toms
                # Pitched sine waves with medium decay
                if note_number in [41, 43]:  # Floor Toms
                    tom_freq = 80  # Low frequency
                elif note_number in [45, 47]:  # Mid Toms
                    tom_freq = 120  # Mid frequency
                else:  # High Toms
                    tom_freq = 180  # Higher frequency
                
                waveform = np.sin(2 * np.pi * tom_freq * t)
                decay = np.exp(-t * 12)
                return waveform * envelope * decay
            
            # Cymbals
            elif note_number in [49, 51, 52, 53, 55, 57]:  # Crash and Ride Cymbals
                # Complex noise with slow decay
                noise = np.random.rand(len(t)) * 2 - 1
                # Add some high frequencies for metallic sound
                for i in range(3, 10):
                    noise += 0.1 / i * np.sin(2 * np.pi * 500 * i * t)
                
                # Longer decay for cymbals
                decay = np.exp(-t * 4)
                return noise * envelope * decay
            
            # Other percussion (default case)
            else:
                # Generic percussion sound based on frequency
                noise = np.random.rand(len(t)) * 2 - 1
                waveform = 0.5 * np.sin(2 * np.pi * frequency * t) + 0.5 * noise
                decay = np.exp(-t * 10)
                return waveform * envelope * decay
        
        else:  # "Synth" (default)
            # Simple synth with multiple waveforms
            waveform = 0.4 * np.sin(2 * np.pi * frequency * t)  # Sine
            # Add square wave component
            square = 0.3 * np.sign(np.sin(2 * np.pi * frequency * t))
            # Add sawtooth component
            sawtooth = 0.3 * ((2 * (frequency * t - np.floor(0.5 + frequency * t))) % 2)
            
            return (waveform + square + sawtooth) * envelope
    
    def convert_midi_to_audio(self, midi, instrument_type, sample_rate, volume):
        try:
            # Get tempo from MIDI file (default to 120 BPM if not specified)
            tempo = 500000  # Default tempo (microseconds per quarter note)
            for track in midi.tracks:
                for msg in track:
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                        break
            
            # Calculate total duration in seconds
            total_time = 0
            last_event_time = 0
            has_notes = False
            
            for track in midi.tracks:
                track_time = 0
                notes_in_track = False
                
                for msg in track:
                    if hasattr(msg, 'time'):
                        track_time += msg.time
                        if msg.type == 'note_on' and hasattr(msg, 'velocity') and msg.velocity > 0:
                            notes_in_track = True
                            has_notes = True
                            last_event_time = track_time
                        elif (msg.type == 'note_off' or (msg.type == 'note_on' and hasattr(msg, 'velocity') and msg.velocity == 0)):
                            last_event_time = track_time
                
                total_time = max(total_time, track_time)
            
            # If we found notes, use the last note event time plus some padding
            if has_notes:
                total_time = last_event_time + 240  # Add a small buffer (240 ticks) for note releases
            
            # Convert ticks to seconds using tempo
            seconds_per_tick = tempo / (midi.ticks_per_beat * 1000000.0)
            total_time = total_time * seconds_per_tick
            
            # Ensure we have some duration
            total_time = max(total_time, 0.5)  # At least 0.5 second
            
            print(f"MIDI duration: {total_time:.2f} seconds")
            
            # Create empty audio buffer
            audio_length = int(total_time * sample_rate)
            audio_buffer = np.zeros(audio_length)
            
            # Process MIDI messages from all tracks
            for track in midi.tracks:
                current_time = 0
                active_notes = {}  # {note: (start_time, velocity)}
                
                for msg in track:
                    if hasattr(msg, 'time'):
                        current_time += msg.time * seconds_per_tick
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        # Start a new note
                        active_notes[msg.note] = (current_time, msg.velocity)
                    
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        # End a note
                        if msg.note in active_notes:
                            start_time, velocity = active_notes[msg.note]
                            duration = current_time - start_time
                            
                            # Generate note audio using instrument-specific synthesis
                            frequency = 440.0 * (2.0 ** ((msg.note - 69) / 12.0))  # Convert MIDI note to frequency
                            note_samples = int(duration * sample_rate)
                            if note_samples > 0:
                                t = np.linspace(0, duration, note_samples, False)
                                # Simple envelope to avoid clicks
                                envelope = np.ones_like(t)
                                attack = int(0.01 * sample_rate)
                                release = int(0.01 * sample_rate)
                                if len(envelope) > attack:
                                    envelope[:attack] = np.linspace(0, 1, attack)
                                if len(envelope) > release:
                                    envelope[-release:] = np.linspace(1, 0, release)
                                
                                # Generate waveform based on instrument type
                                note_audio = self.generate_instrument_waveform(
                                    frequency, t, instrument_type, envelope, msg.note
                                ) * (velocity / 127.0) * volume
                                
                                # Add to buffer with proper timing
                                start_idx = int(start_time * sample_rate)
                                end_idx = start_idx + len(note_audio)
                                if end_idx > len(audio_buffer):
                                    audio_buffer = np.pad(audio_buffer, (0, end_idx - len(audio_buffer)))
                                audio_buffer[start_idx:end_idx] += note_audio
                            
                            del active_notes[msg.note]
            
            # Normalize audio if we have any content
            if len(audio_buffer) > 0 and np.max(np.abs(audio_buffer)) > 0:
                audio_buffer = audio_buffer / np.max(np.abs(audio_buffer))
            
            # Convert to stereo
            audio_buffer = np.stack([audio_buffer, audio_buffer])
            
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_buffer).float()
            
            print(f"Generated audio length: {len(audio_buffer[0])/sample_rate:.2f} seconds")
            
            return ({
                "waveform": audio_tensor.unsqueeze(0),  # Add batch dimension
                "sample_rate": sample_rate
            },)
            
        except Exception as e:
            # If anything goes wrong, return empty audio
            print(f"Error in MIDIToAudio: {str(e)}")
            empty_audio = torch.zeros((1, 2, 1))  # 1 batch, 2 channels, 1 sample
            return ({
                "waveform": empty_audio,
                "sample_rate": sample_rate
            },)

def calculate_midi_total_measures(midi_data):
    """Calculate the total number of measures in the MIDI file"""
    # Get time signature (defaults to 4/4)
    time_sig_numerator = 4
    time_sig_denominator = 4
    
    for track in midi_data.tracks:
        for msg in track:
            if msg.type == 'time_signature':
                time_sig_numerator = msg.numerator
                time_sig_denominator = msg.denominator
                break
    
    # Calculate total ticks
    total_ticks = 0
    for track in midi_data.tracks:
        track_ticks = 0
        for msg in track:
            if hasattr(msg, 'time'):
                track_ticks += msg.time
        total_ticks = max(total_ticks, track_ticks)
    
    # Calculate ticks per measure
    ticks_per_beat = midi_data.ticks_per_beat
    ticks_per_measure = ticks_per_beat * 4 * (time_sig_numerator / time_sig_denominator)
    
    # Calculate total measures
    total_measures = math.ceil(total_ticks / ticks_per_measure)
    return total_measures, time_sig_numerator, time_sig_denominator

def convert_measures_to_ticks_range(midi_data, start_measure, start_beat, end_measure, end_beat):
    """Convert musical measure range to MIDI tick range"""
    # Get time signature (defaults to 4/4)
    time_sig_numerator = 4
    time_sig_denominator = 4
    
    for track in midi_data.tracks:
        for msg in track:
            if msg.type == 'time_signature':
                time_sig_numerator = msg.numerator
                time_sig_denominator = msg.denominator
                break
    
    # Calculate ticks per beat and measure
    ticks_per_beat = midi_data.ticks_per_beat
    beats_per_measure = time_sig_numerator
    
    # Adjust start measure/beat to 0-indexed for calculation
    start_measure_index = start_measure - 1
    start_beat_index = start_beat - 1
    
    # Calculate start tick
    start_tick = (start_measure_index * beats_per_measure + start_beat_index) * ticks_per_beat
    
    # Calculate end tick
    if end_measure > 0:
        end_measure_index = end_measure - 1
        end_beat_index = end_beat - 1
        end_tick = (end_measure_index * beats_per_measure + end_beat_index) * ticks_per_beat
    else:
        end_tick = float('inf')
    
    return start_tick, end_tick

class MIDIToText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "midi": ("MIDI",),
                "max_events": ("INT", {"default": 30, "min": 5, "max": 100, "step": 1}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    FUNCTION = "translate_midi"
    CATEGORY = "RyanOnTheInside/Audio/MIDI"

    def note_name(self, midi_number):
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (midi_number // 12) - 1
        name = notes[midi_number % 12]
        return f"{name}{octave}"

    def estimate_key(self, note_counts):
        """
        Uproszczony algorytm dopasowania profilu tonacji.
        Zwraca najbardziej prawdopodobną tonację (np. 'A minor' lub 'C major').
        """
        # Wzorce stopni dla skali dur i moll (1 = nuta należy do skali, 0 = poza skalą)
        major_profile = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]
        minor_profile = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        
        best_fit_key = "C major"
        max_score = -1

        for root in range(12):
            # Testujemy dur
            major_score = sum(note_counts[(root + i) % 12] * major_profile[i] for i in range(12))
            if major_score > max_score:
                max_score = major_score
                best_fit_key = f"{note_names[root]} major"
            
            # Testujemy moll
            minor_score = sum(note_counts[(root + i) % 12] * minor_profile[i] for i in range(12))
            if minor_score > max_score:
                max_score = minor_score
                best_fit_key = f"{note_names[root]} minor"

        return best_fit_key

    def get_register_description(self, min_note, max_note):
        """Mapuje numery MIDI na opis fizycznego rejestru instrumentu."""
        desc = []
        if min_note < 48: # Poniżej C3
            desc.append("deep heavy bass notes")
        elif min_note < 60: # Poniżej C4
            desc.append("warm mid-low foundation")
        
        if max_note > 72: # Powyżej C5
            desc.append("bright, delicate high-register keys")
        elif max_note > 60:
            desc.append("clear mid-range melody")
            
        return " coupled with ".join(desc) if desc else "balanced mid-range frequencies"

    def translate_midi(self, midi, max_events):
        import mido
        
        bpm = 120  # Domyślne
        for track in midi.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    bpm = int(mido.tempo2bpm(msg.tempo))
                    break

        raw_events = []
        note_counts = [0] * 12  # Do analizy tonacji
        midi_numbers = []       # Do analizy rejestru
        ticks_between_notes = []
        
        last_note_tick = None
        current_tick = 0
        
        for track in midi.tracks:
            current_tick = 0
            for msg in track:
                current_tick += msg.time
                if msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
                    raw_events.append((current_tick, msg.note))
                    note_counts[msg.note % 12] += 1
                    midi_numbers.append(msg.note)
                    
                    if last_note_tick is not None:
                        ticks_between_notes.append(current_tick - last_note_tick)
                    last_note_tick = current_tick
        
        raw_events.sort(key=lambda x: x[0])

        if not raw_events:
            return ("MIDI Song Data: [No notes found in MIDI file]",)

        # 1. Analiza Tonacji i Rejestru
        detected_key = self.estimate_key(note_counts)
        register_desc = self.get_register_description(min(midi_numbers), max(midi_numbers))

        # 2. Analiza gęstości rytmu
        avg_tick_diff = sum(ticks_between_notes) / len(ticks_between_notes) if ticks_between_notes else 0
        ticks_per_beat = midi.ticks_per_beat
        
        if avg_tick_diff == 0:
            rhythm_desc = "static sustained single-note performance"
        elif avg_tick_diff < (ticks_per_beat / 2): # Gęściej niż ósemki
            rhythm_desc = "fast, fluid, and flowing arpeggiated movement"
        elif avg_tick_diff < ticks_per_beat: # Ćwierćnuty/ósemki
            rhythm_desc = "steady, moderate rhythmic cadence"
        else: # Półnuty/całe nuty
            rhythm_desc = "slow, spacious, heavily sustained and drifting progression"

        # 3. Grupowanie i wyciąganie unikalnych akordów/sekwencji
        tolerance = ticks_per_beat // 4
        unique_chords = []
        current_chord = [self.note_name(raw_events[0][1])]
        last_tick = raw_events[0][0]

        for tick, note_num in raw_events[1:]:
            note = self.note_name(note_num)
            if tick - last_tick <= tolerance:
                current_chord.append(note)
            else:
                current_chord = list(sorted(set(current_chord)))
                chord_str = f"chord with notes {', '.join(current_chord)}" if len(current_chord) > 1 else f"single note {current_chord[0]}"
                if chord_str not in unique_chords:
                    unique_chords.append(chord_str)
                current_chord = [note]
                last_tick = tick
        
        current_chord = list(sorted(set(current_chord)))
        chord_str = f"chord with notes {', '.join(current_chord)}" if len(current_chord) > 1 else f"single note {current_chord[0]}"
        if chord_str not in unique_chords:
            unique_chords.append(chord_str)

        # Budujemy ponumerowaną, czystą sekwencję tekstową kroków harmonicznych
        chord_steps = [f"step {i+1} playing {chord}" for i, chord in enumerate(unique_chords[:8])]
        featured_harmonies = ", then ".join(chord_steps)

        # Formułujemy czysty wyjściowy opis - całkowicie usuwamy nawiasy klamrowe i kwadratowe
        output_text = (
            f"MIDI Song Data:\n"
            f"- BPM: {bpm} BPM\n"
            f"- Harmonic Key Profile: Written in the scale of {detected_key}\n"
            f"- Sonic Range & Register: Spans from {register_desc}\n"
            f"- Rhythmic Movement & Density: Characterized by a {rhythm_desc}\n"
            f"- Primary Harmonic Structures: Follows a distinct progression of {featured_harmonies}"
        )
        return (output_text,)

class MIDIToBehaviorProfile:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "midi": ("MIDI",),
                "max_chord_steps": ("INT", {"default": 8, "min": 4, "max": 16, "step": 1}),
                "phrase_silence_threshold": ("FLOAT", {"default": 0.5, "min": 0.1, "max": 2.0, "step": 0.1, 
                                                     "tooltip": "Sekundy ciszy uznawane za granicę frazy"}),
            }
        }
    
    RETURN_TYPES = ("STRING", "INT", "INT", "FLOAT", "INT", "INT")  # Behavior text, BPM, Total measures, Loop compatibility score, metrum np 3, 4 co daje 3/4
    RETURN_NAMES = ("behavior_profile", "bpm", "midi_measures", "loop_score", "beats_per_measure", "beat_value")
    FUNCTION = "analyze_midi"
    CATEGORY = "RyanOnTheInside/Audio/MIDI"

    def __init__(self):
        self.note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        
    def note_to_name(self, midi_num):
        return f"{self.note_names[midi_num % 12]}{(midi_num // 12) - 1}"

    def get_interval_name(self, semitones):
        """Nazwa interwału dla opisu ruchu"""
        intervals = {
            0: "unison", 1: "minor second", 2: "major second", 3: "minor third",
            4: "major third", 5: "perfect fourth", 7: "perfect fifth",
            9: "major sixth", 10: "minor seventh", 12: "octave"
        }
        return intervals.get(abs(semitones), f"{abs(semitones)} semitones")

    def chord_to_function(self, notes, key_root, is_minor):
        """
        Prosta analiza funkcjonalna. Zwraca np. "I", "IV", "V", "vi".
        Zakłada, że notes to lista nazw nut (np. ['C4', 'E4', 'G4'])
        """
        if not notes:
            return "rest"
            
        # Znajdź root akordu (najniższa nuta)
        root_note = min(notes, key=lambda x: int(x[-1]) * 100 + self.note_names.index(x[:-1]))
        root_pitch = self.note_names.index(root_note[:-1])
        
        # Oblicz stopień względem tonacji
        degree = (root_pitch - key_root) % 12
        
        # Mapowanie stopni na funkcje (dla major i minor)
        if is_minor:
            # A minor: A=0 (i), B=2 (ii°), C=3 (III), D=5 (iv), E=7 (v), F=8 (VI), G=10 (VII)
            functions = {0: "i", 3: "III", 5: "iv", 7: "v", 8: "VI", 10: "VII"}
        else:
            # C major: C=0 (I), D=2 (ii), E=4 (iii), F=5 (IV), G=7 (V), A=9 (vi), B=11 (vii°)
            functions = {0: "I", 2: "ii", 4: "iii", 5: "IV", 7: "V", 9: "vi", 11: "vii°"}
            
        return functions.get(degree, f"chromatic({degree})")

    def analyze_midi(self, midi, max_chord_steps, phrase_silence_threshold):
        import mido
        
        # --- 1. GLOBALNE PARAMETRY ---
        bpm = 120
        time_sig = (4, 4)  # domyślne 4/4
        key_sig = None     # opcjonalnie z MIDI
        
        total_ticks = 0
        all_notes = []     # (tick, note, velocity, track)
        
        # --- 2. ZBIERANIE DANYCH Z TRACKÓW ---
        for track_idx, track in enumerate(midi.tracks):
            current_tick = 0
            for msg in track:
                current_tick += msg.time
                
                if msg.type == 'set_tempo':
                    bpm = int(mido.tempo2bpm(msg.tempo))
                elif msg.type == 'time_signature':
                    time_sig = (msg.numerator, msg.denominator)
                elif msg.type == 'key_signature':
                    key_sig = msg.key  # np. 'C', 'Am'
                elif msg.type == 'note_on' and msg.velocity > 0:
                    all_notes.append({
                        'tick': current_tick,
                        'note': msg.note,
                        'velocity': msg.velocity,
                        'track': track_idx
                    })
                    
            total_ticks = max(total_ticks, current_tick)
        
        if not all_notes:
            return ("MIDI Behavior Profile: [No musical data]", 120, 0, 0.0)
        
        # Sortuj wszystkie nuty globalnie (po czasie)
        all_notes.sort(key=lambda x: x['tick'])
        
        # --- 3. ANALIZA TONACJI I REJESTRU ---
        note_counts = [0] * 12
        velocities = []
        midi_nums = []
        
        for n in all_notes:
            note_counts[n['note'] % 12] += 1
            velocities.append(n['velocity'])
            midi_nums.append(n['note'])
        
        detected_key = MIDIToText.estimate_key(self, note_counts)  # Twoja metoda
        is_minor = "minor" in detected_key.lower()
        key_root = self.note_names.index(detected_key.split()[0])
        
        min_note, max_note = min(midi_nums), max(midi_nums)
        register_desc = MIDIToText.get_register_description(self, min_note, max_note)
        
        # --- 4. ANALIZA DYNAMIKI ---
        avg_velocity = sum(velocities) / len(velocities)
        velocity_variance = sum((v - avg_velocity)**2 for v in velocities) / len(velocities)
        
        if avg_velocity > 100:
            dynamic_char = "aggressive and loud"
        elif avg_velocity > 80:
            dynamic_char = "moderately strong"
        elif avg_velocity > 60:
            dynamic_char = "gentle and restrained"
        else:
            dynamic_char = "delicate and soft"
            
        if velocity_variance > 400:
            dynamic_behavior = f"highly dynamic with {dynamic_char} accents"
        else:
            dynamic_behavior = f"consistently {dynamic_char}"

        # --- 5. STRUKTURA CZASOWA (TAKTY I FRazy) ---
        ticks_per_beat = midi.ticks_per_beat
        beats_per_measure = time_sig[0]
        ticks_per_measure = ticks_per_beat * beats_per_measure
        
        total_measures = max(1, int(total_ticks / ticks_per_measure))
        
        # Oblicz sekundy na tick (dla phrase detection)
        seconds_per_tick = (60.0 / bpm) / ticks_per_beat
        silence_ticks_threshold = phrase_silence_threshold / seconds_per_tick
        
        # --- 6. DETEKCJA FRAZ (granice crossfade'u) ---
        phrase_points = [0]  # początek
        
        last_note_end = all_notes[0]['tick']
        for i in range(1, len(all_notes)):
            gap = all_notes[i]['tick'] - last_note_end
            if gap > silence_ticks_threshold:
                phrase_points.append(all_notes[i]['tick'])
            last_note_end = max(last_note_end, all_notes[i]['tick'] + ticks_per_beat)  # przybliżenie długości nuty
        
        phrase_behavior = f"natural phrase breaks every approximately {total_measures // max(1, len(phrase_points))} measures"
        
        # --- 7. PROGRESJA HARMONICZNA Z FUNKCJAMI ---
        tolerance = ticks_per_beat // 4  # 1/16 nuty
        
        # Grupowanie w akordy (poprawione - nie resetuje last_tick między trackami)
        chords = []
        current_chord_notes = []
        current_chord_start = all_notes[0]['tick']
        
        for note_data in all_notes:
            tick = note_data['tick']
            note_name = self.note_to_name(note_data['note'])
            
            if tick - current_chord_start <= tolerance:
                current_chord_notes.append(note_name)
            else:
                if current_chord_notes:
                    unique_notes = list(sorted(set(current_chord_notes)))
                    func = self.chord_to_function(unique_notes, key_root, is_minor)
                    chords.append({
                        'tick': current_chord_start,
                        'notes': unique_notes,
                        'function': func
                    })
                current_chord_notes = [note_name]
                current_chord_start = tick
        
        # Ostatni akord
        if current_chord_notes:
            unique_notes = list(sorted(set(current_chord_notes)))
            func = self.chord_to_function(unique_notes, key_root, is_minor)
            chords.append({'tick': current_chord_start, 'notes': unique_notes, 'function': func})
        
        # --- 8. LOOP COMPATIBILITY (czy zaczyna i kończy się kompatybilnie) ---
        if len(chords) >= 2:
            first_func = chords[0]['function']
            last_func = chords[-1]['function']
            
            # Kompatybilne kadencje: I-i, V-I, iv-i (dla minor), itp.
            compatible_endings = [
                (first_func, first_func),  # Ten sam akord
                ('V', 'I'), ('V', 'i'),    # Dominanta do toniki
                ('v', 'i'), ('VII', 'i'),  # Dla minor
                ('IV', 'I'), ('iv', 'i')   # Subdominanta do toniki
            ]
            
            loop_score = 1.0 if (first_func, last_func) in compatible_endings else 0.5
            if first_func == last_func:
                loop_desc = "perfect loop compatibility - starts and ends on the same harmonic function"
            elif loop_score > 0.5:
                loop_desc = "cadence-compatible loop structure"
            else:
                loop_desc = "open-ended harmonic structure - suitable for linear progression rather than seamless loop"
        else:
            loop_score = 0.5
            loop_desc = "insufficient harmonic data for loop analysis"

        # --- 9. BEHAVIOR PROFILE TEXT ---
        # Budujemy progresję funkcji (max max_chord_steps)
        func_progression = [c['function'] for c in chords[:max_chord_steps]]
        func_str = " -> ".join(func_progression) if func_progression else "single tonic anchor"
        
        # Rhythm character (z poprzedniego kodu, ale poprawiony)
        tick_gaps = []
        for i in range(1, len(all_notes)):
            gap = all_notes[i]['tick'] - all_notes[i-1]['tick']
            if gap > 0:
                tick_gaps.append(gap)
        
        if tick_gaps:
            avg_gap = sum(tick_gaps) / len(tick_gaps)
            if avg_gap < ticks_per_beat / 2:
                rhythm_char = "dense, active texture with subdivided beats"
            elif avg_gap < ticks_per_beat:
                rhythm_char = "steady rhythmic pulse with moderate activity"
            else:
                rhythm_char = "spacious, sustained harmonic movement with breathing room"
        else:
            rhythm_char = "single sustained texture"

        beats_per_measure = int(time_sig[0]) if time_sig and len(time_sig) > 0 else 4
        beat_value = int(time_sig[1]) if time_sig and len(time_sig) > 1 else 4

        # --- 10. FINALNY OUTPUT ---
        behavior_text = f"""MIDI MUSICAL BEHAVIOR PROFILE

Usage: Treat this as compositional DNA, not a melody to copy. All game music variations must preserve these behaviors for crossfade compatibility.

CORE GRID:
Tempo: {bpm} BPM locked
Meter: {time_sig[0]}/{time_sig[1]}
Loop Character: {loop_desc}

HARMONIC BEHAVIOR:
Key Center: {detected_key}
Harmonic Progression: {func_str}
Cadence Logic: The music moves through {len(func_progression)} distinct harmonic functions, establishing a clear tonal gravity suitable for thematic development.

PHRASE ARCHITECTURE:
{phrase_behavior}
Natural silence gaps detected at {len(phrase_points)} points, providing clean crossfade boundaries for adaptive music systems.

SONIC ARCHITECTURE:
Register: {register_desc}
Dynamic Character: {dynamic_behavior} (average velocity {int(avg_velocity)}/127)

RHYTHMIC BEHAVIOR:
{rhythm_char}
The pulse is optimized for {time_sig[0]}/{time_sig[1]} feel with internal spacing that allows counter-melody entries during sustained harmonic areas.

CROSSFADE RULES:
Maintain {bpm} BPM, {time_sig[0]}/{time_sig[1]} meter, and {detected_key} key center across all variations. 
Preserve the harmonic function sequence {func_str.split(' -> ')[0] if ' -> ' in func_str else func_str} -> ... -> {func_str.split(' -> ')[-1] if ' -> ' in func_str else func_str} for compatibility.
Use the detected phrase boundaries for transition points between calm, tension, and combat versions."""

        return (behavior_text, bpm, total_measures, loop_score, beats_per_measure, beat_value)

class CounterMelodyInstrumentSelector:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "detected_instruments": ("STRING", {"forceInput": True}),
                "allowed_counter_instruments": ("STRING", {
                    "default": "Trumpet, Violin, Flute, Classical Guitar, Oboe, Piano",
                    "multiline": True
                }),
                "preferred_register": (["high_register", "mid_register"], {"default": "high_register"}),
                "max_instruments": ("INT", {"default": 3, "min": 1, "max": 4, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("best_single_instrument", "filtered_instrument_list",)
    FUNCTION = "select_instruments"
    CATEGORY = "RyanOnTheInside/Audio/Management"

    def normalize(self, text):
        import re
        text = text.lower()
        text = text.replace("pianino", "piano")
        text = text.replace("percusion", "percussion")
        text = text.replace("bass guitar", "bass guitar")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def select_instruments(self, detected_instruments, allowed_counter_instruments, preferred_register, max_instruments):
        detected_text = self.normalize(detected_instruments)

        allowed = [
            self.normalize(x.strip())
            for x in allowed_counter_instruments.split(",")
            if x.strip()
        ]

        aliases = {
            "classical guitar": ["classical guitar", "nylon guitar", "acoustic guitar", "guitar"],
            "piano": ["piano", "pianino", "keys"],
            "violin": ["violin", "fiddle", "strings"],
            "trumpet": ["trumpet", "horn", "brass"],
            "flute": ["flute"],
            "oboe": ["oboe"],
        }

        instrument_weights = {
            "trumpet": {"register": "high_register", "score": 5},
            "violin": {"register": "high_register", "score": 5},
            "flute": {"register": "high_register", "score": 4},
            "oboe": {"register": "high_register", "score": 4},
            "classical guitar": {"register": "mid_register", "score": 3},
            "piano": {"register": "mid_register", "score": 2},
        }

        scored = []

        for inst in allowed:
            possible_names = aliases.get(inst, [inst])
            matched = any(alias in detected_text for alias in possible_names)

            if matched:
                weight = instrument_weights.get(inst, {"register": "mid_register", "score": 1})
                score = weight["score"]

                if weight["register"] == preferred_register:
                    score += 2

                scored.append((inst, score))

        if not scored:
            for inst in allowed:
                weight = instrument_weights.get(inst, {"register": "mid_register", "score": 1})
                score = weight["score"]

                if weight["register"] == preferred_register:
                    score += 2

                scored.append((inst, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        top = scored[:max_instruments]

        def pretty(name):
            return " ".join(word.capitalize() for word in name.split())

        best_single = pretty(top[0][0]) if top else "Trumpet"
        filtered_list = ", ".join(pretty(x[0]) for x in top)

        return best_single, filtered_list
    
@apply_tooltips
class MIDILoader:
    """Loads MIDI files for processing in ComfyUI with options for selecting specific measures."""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "midi_file": (folder_paths.get_filename_list("midi_files"),),
                "track_selection": (["all"],),
                "start_measure": ("INT", {"default": 1, "min": 1, "step": 1}),
                "start_beat": ("INT", {"default": 1, "min": 1, "step": 1}),
                "end_measure": ("INT", {"default": 0, "min": 0, "step": 1, "tooltip": "End measure (0 = all remaining measures)"}),
                "end_beat": ("INT", {"default": 1, "min": 1, "step": 1, "tootip": "End beat"})
            }
        }

    RETURN_TYPES = ("MIDI",)
    FUNCTION = "load_midi"
    CATEGORY = "RyanOnTheInside/Audio/MIDI"
    
    def load_midi(self, midi_file, track_selection, start_measure=1, start_beat=1, end_measure=0, end_beat=1):
        import mido
        try:
            midi_path = folder_paths.get_full_path("midi_files", midi_file)
            if not midi_path or not os.path.exists(midi_path):
                raise FileNotFoundError(f"MIDI file not found: {midi_file}")

            # Load the MIDI file
            midi_data = mido.MidiFile(midi_path)
            
            # Apply track selection if not "all"
            if track_selection != "all":
                track_index_str = track_selection.split(':')[0].strip()
                if track_index_str.isdigit():
                    track_index = int(track_index_str)
                    # Create a new MIDI file with only the selected track
                    selected_midi = mido.MidiFile(ticks_per_beat=midi_data.ticks_per_beat)
                    
                    # First, add any metadata tracks (typically track 0 in type 1 MIDI files)
                    if midi_data.type == 1 and track_index > 0:
                        selected_midi.tracks.append(midi_data.tracks[0])
                    
                    # Add the selected track
                    if track_index < len(midi_data.tracks):
                        selected_midi.tracks.append(midi_data.tracks[track_index])
                    
                    midi_data = selected_midi
            
            # Apply measure slicing if needed
            if (start_measure > 1 or start_beat > 1 or end_measure > 0) and midi_data.tracks:
                # Get total measures in the file for validation
                total_measures, _, _ = calculate_midi_total_measures(midi_data)
                
                # If end measure is 0, use the total measures
                if end_measure == 0:
                    end_measure = total_measures
                
                # Convert musical measures to ticks
                start_tick, end_tick = convert_measures_to_ticks_range(midi_data, start_measure, start_beat, end_measure, end_beat)
                
                # The total duration in ticks is EXACTLY end_tick - start_tick
                total_tick_duration = end_tick - start_tick
                
                # Create a new MIDI file with the selected measures
                trimmed_midi = mido.MidiFile(ticks_per_beat=midi_data.ticks_per_beat)
                
                for track in midi_data.tracks:
                    new_track = mido.MidiTrack()
                    trimmed_midi.tracks.append(new_track)
                    
                    # Copy important metadata messages first
                    for msg in track:
                        if not hasattr(msg, 'time'):
                            if msg.type in ['track_name', 'time_signature', 'key_signature', 'set_tempo']:
                                new_track.append(msg.copy())
                    
                    # Collect events within the time range
                    note_events = []
                    active_notes = {}  # {note_num: tick_time_started}
                    notes_active_before_range = {}  # Track notes that started before our range
                    current_tick = 0
                    
                    # First pass: collect all note on/off events, tracking notes that cross boundaries
                    for msg in track:
                        if not hasattr(msg, 'time'):
                            continue
                        
                        current_tick += msg.time
                        
                        # Handle note_on events
                        if msg.type == 'note_on' and msg.velocity > 0:
                            # Note starting before our range
                            if current_tick < start_tick:
                                notes_active_before_range[msg.note] = current_tick
                            # Note starting within our range
                            elif current_tick <= end_tick:
                                active_notes[msg.note] = current_tick
                                note_events.append((current_tick, msg.copy()))
                        
                        # Handle note_off events
                        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                            # Handle notes that started before our range but end within it
                            if msg.note in notes_active_before_range:
                                if current_tick >= start_tick and current_tick <= end_tick:
                                    # Create a new note_on at the start boundary
                                    new_note_on = mido.Message('note_on', note=msg.note, velocity=64, time=0)
                                    note_events.append((start_tick, new_note_on))
                                    # Add the note_off event
                                    note_events.append((current_tick, msg.copy()))
                                del notes_active_before_range[msg.note]
                            
                            # Handle notes that started within our range
                            elif msg.note in active_notes:
                                # If note ends within our range, add the note_off event
                                if current_tick <= end_tick:
                                    note_events.append((current_tick, msg.copy()))
                                # If note would end outside our range, add a note_off at the end boundary
                                else:
                                    new_note_off = mido.Message('note_off', note=msg.note, velocity=0, time=0)
                                    note_events.append((end_tick, new_note_off))
                                del active_notes[msg.note]
                        
                        # Include other MIDI events within the time range
                        elif current_tick >= start_tick and current_tick <= end_tick:
                            if msg.type in ['set_tempo', 'control_change', 'program_change', 'pitchwheel']:
                                note_events.append((current_tick, msg.copy()))
                    
                    # Add note_off events at end boundary for any notes still active at the end
                    for note in active_notes:
                        new_note_off = mido.Message('note_off', note=note, velocity=0, time=0)
                        note_events.append((end_tick, new_note_off))
                    
                    # Sort events by tick time
                    note_events.sort(key=lambda x: x[0])
                    
                    # Add events to the new track with adjusted timing
                    prev_tick = start_tick
                    
                    for tick, msg in note_events:
                        # Adjust timing relative to previous event
                        adjusted_msg = msg.copy()
                        adjusted_msg.time = tick - prev_tick
                        prev_tick = tick
                        
                        new_track.append(adjusted_msg)
                    
                    # Calculate how many ticks remain until the exact end_tick
                    remaining_ticks = start_tick + total_tick_duration - prev_tick
                    
                    # Add end of track marker at exactly the right position
                    end_track = mido.MetaMessage('end_of_track')
                    end_track.time = max(0, remaining_ticks)
                    new_track.append(end_track)
                
                midi_data = trimmed_midi
            
            return (midi_data,)

        except Exception as e:
            raise RuntimeError(f"Error loading MIDI file: {type(e).__name__}: {str(e)}")
    
    @classmethod
    def analyze_midi(cls, midi_path, start_measure=1, start_beat=1, end_measure=0, end_beat=1):
        import mido
        midi_data = mido.MidiFile(midi_path)
        
        # Get the total measures
        total_measures, time_sig_num, time_sig_denom = calculate_midi_total_measures(midi_data)
        
        # If end measure is 0, use the total measures
        if end_measure == 0:
            end_measure = total_measures
        
        # Convert measures to ticks if measure filtering is applied
        if start_measure > 1 or start_beat > 1 or end_measure < total_measures:
            start_tick, end_tick = convert_measures_to_ticks_range(midi_data, start_measure, start_beat, end_measure, end_beat)
        else:
            start_tick = 0
            end_tick = float('inf')
        
        tracks = ["all"]
        all_notes = set()
        track_notes = {}
        for i, track in enumerate(midi_data.tracks):
            track_notes[str(i)] = set()
            current_tick = 0
            
            # Keep track of notes that start within range
            active_notes = set()
            
            for msg in track:
                if hasattr(msg, 'time'):
                    current_tick += msg.time
                
                # Only consider notes within our measure range
                if current_tick >= start_tick and current_tick <= end_tick:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        track_notes[str(i)].add(msg.note)
                        all_notes.add(msg.note)
                        active_notes.add(msg.note)
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        if msg.note in active_notes:
                            active_notes.remove(msg.note)
            
            if len(track_notes[str(i)]) == 0:
                tracks.append(f"{i}: (Empty)")
            else:
                tracks.append(f"{i}: {getattr(track, 'name', '') or f'Track {i}'}")
        
        return {
            "tracks": tracks,
            "all_notes": ",".join(map(str, sorted(set(all_notes)))),
            "track_notes": {k: ",".join(map(str, sorted(v))) for k, v in track_notes.items()},
            "total_measures": total_measures,
            "time_signature": f"{time_sig_num}/{time_sig_denom}"
        }
    
    @classmethod
    def VALIDATE_INPUTS(cls, midi_file, track_selection, start_measure=1, start_beat=1, end_measure=0, end_beat=1):
        import mido
        midi_path = folder_paths.get_full_path("midi_files", midi_file)
        if not midi_path or not os.path.isfile(midi_path):
            return f"MIDI file not found: {midi_file}"
        
        # Check if the file has a .mid or .midi extension
        if not midi_file.lower().endswith(('.mid', '.midi')):
            return f"Invalid file type. Expected .mid or .midi file, got: {midi_file}"
        
        if start_measure < 1:
            return f"Start measure must be at least 1, got: {start_measure}"
        
        if start_beat < 1:
            return f"Start beat must be at least 1, got: {start_beat}"
        
        if end_measure < 0:
            return f"End measure cannot be negative, got: {end_measure}"
        
        if end_beat < 1:
            return f"End beat must be at least 1, got: {end_beat}"
        
        # Check if the start measure is valid for this MIDI file
        try:
            midi_data = mido.MidiFile(midi_path)
            total_measures, _, _ = calculate_midi_total_measures(midi_data)
            
            if start_measure > total_measures:
                return f"Start measure {start_measure} exceeds the total measures in the file ({total_measures})"
            
            if end_measure > 0 and end_measure > total_measures:
                return f"End measure {end_measure} exceeds the total measures in the file ({total_measures})"
            
            if end_measure > 0 and end_measure < start_measure:
                return f"End measure {end_measure} cannot be less than start measure {start_measure}"
                
            if end_measure == start_measure and end_beat < start_beat:
                return f"When start and end measures are the same, end beat {end_beat} cannot be less than start beat {start_beat}"
        except Exception as e:
            return f"Error validating MIDI file: {str(e)}"
        
        return True

# Server routes for MIDI file handling
routes = PromptServer.instance.routes

@routes.post('/get_track_notes')
async def get_track_notes(request):
    data = await request.json()
    midi_file = data.get('midi_file')
    start_measure = data.get('start_measure', 1)
    start_beat = data.get('start_beat', 1)
    end_measure = data.get('end_measure', 0)
    end_beat = data.get('end_beat', 1)

    if not midi_file:
        return web.json_response({"error": "Missing required parameters"}, status=400)

    midi_path = folder_paths.get_full_path("midi_files", midi_file)
    if not midi_path or not os.path.exists(midi_path):
        return web.json_response({"error": "MIDI file not found"}, status=404)

    # Analyze MIDI file
    analysis = MIDILoader.analyze_midi(midi_path, start_measure, start_beat, end_measure, end_beat)
    return web.json_response(analysis)

@routes.post('/upload_midi')
async def upload_midi(request):
    data = await request.post()
    midi_file = data['file']
    
    if midi_file and midi_file.filename:
        safe_filename = os.path.basename(midi_file.filename)
        
        midi_dir = folder_paths.get_folder_paths("midi_files")[0]
        
        if not os.path.exists(midi_dir):
            os.makedirs(midi_dir, exist_ok=True)
        
        midi_path = os.path.join(midi_dir, safe_filename)

        with open(midi_path, 'wb') as f:
            shutil.copyfileobj(midi_file.file, f)

        midi_files = folder_paths.get_filename_list("midi_files")
        analysis = MIDILoader.analyze_midi(midi_path)

        return web.json_response({
            "status": "success",
            "uploaded_file": safe_filename,
            "midi_files": midi_files,
            "analysis": analysis
        })
    else:
        return web.json_response({"status": "error", "message": "No file uploaded"}, status=400)
    
@routes.post('/refresh_midi_data')
async def refresh_midi_data(request):
    import mido
    data = await request.json()
    midi_file = data.get('midi_file')
    track_selection = data.get('track_selection')
    start_measure = data.get('start_measure', 1)
    start_beat = data.get('start_beat', 1)
    end_measure = data.get('end_measure', 0)
    end_beat = data.get('end_beat', 1)

    if not midi_file:
        return web.json_response({"error": "Missing required parameters"}, status=400)

    midi_path = folder_paths.get_full_path("midi_files", midi_file)
    if not midi_path or not os.path.exists(midi_path):
        return web.json_response({"error": "MIDI file not found"}, status=404)

    # Load the full MIDI data
    midi_data = mido.MidiFile(midi_path)
    
    # Get total measures information
    total_measures, time_sig_num, time_sig_denom = calculate_midi_total_measures(midi_data)
    
    # If end measure is 0, use the total measures
    if end_measure == 0:
        end_measure = total_measures
    
    # Apply track selection and measure filtering
    all_notes = set()
    
    # Convert measures to ticks
    if start_measure > 1 or start_beat > 1 or end_measure < total_measures:
        start_tick, end_tick = convert_measures_to_ticks_range(midi_data, start_measure, start_beat, end_measure, end_beat)
    else:
        start_tick = 0
        end_tick = float('inf')
    
    # Process tracks to collect notes within the time range
    track_notes = {}
    for i, track in enumerate(midi_data.tracks):
        track_notes[str(i)] = set()
        current_tick = 0
        
        # Keep track of notes that start within range
        active_notes = set()
        
        for msg in track:
            if hasattr(msg, 'time'):
                current_tick += msg.time
                
            # Only consider note_on messages with velocity > 0 (actual notes being played)
            if msg.type == 'note_on' and hasattr(msg, 'velocity') and msg.velocity > 0:
                # Check if this note is within our measure range
                if current_tick >= start_tick and current_tick < end_tick:
                    note = msg.note
                    track_notes[str(i)].add(note)
                    active_notes.add(note)
                    # If all tracks are selected or the current track matches selection, add to all_notes
                    if track_selection == "all" or track_selection.startswith(f"{i}:"):
                        all_notes.add(note)
            
            # Remove notes from active set when they're turned off, but don't remove from track_notes
            elif msg.type == 'note_off' or (msg.type == 'note_on' and hasattr(msg, 'velocity') and msg.velocity == 0):
                if msg.note in active_notes:
                    active_notes.remove(msg.note)
    
    # If a specific track is selected but we didn't find any notes, it might be because
    # track selection was changed after note filtering
    if track_selection != "all" and not all_notes:
        track_index = track_selection.split(':')[0]
        if track_index.isdigit() and track_index in track_notes:
            all_notes = track_notes[track_index]
    
    # Format and return the response
    return web.json_response({
        "tracks": ["all"] + [f"{i}: {getattr(track, 'name', '') or f'Track {i}'}" for i, track in enumerate(midi_data.tracks)],
        "all_notes": ",".join(map(str, sorted(all_notes))),
        "track_notes": {k: ",".join(map(str, sorted(v))) for k, v in track_notes.items()},
        "total_measures": total_measures,
        "time_signature": f"{time_sig_num}/{time_sig_denom}"
    })

NODE_CLASS_MAPPINGS = {
    "MIDIToAudio": MIDIToAudio,
    "MIDIToText": MIDIToText,
    "MIDILoader": MIDILoader,
    "CounterMelodyInstrumentSelector" : CounterMelodyInstrumentSelector,
    "MIDIToBehaviorProfile" : MIDIToBehaviorProfile
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIDIToAudio": "MIDI to Audio",
    "MIDIToText": "MIDI to Text Translaton ⚡",
    "MIDILoader": "MIDI Loader",
    "CounterMelodyInstrumentSelector" : "Counter Selector",
    "MIDIToBehaviorProfile" : "MIDI PROFILER"
}