#!/bin/bash

# Zatrzymanie skryptu w przypadku błędu
set -e

echo "=== ROZPOCZYNAM AKTUALIZACJĘ SYSTEMU AUDIO ==="

# 1. Hack parsera MIDI w kontenerze
echo "Krok 1/2: Podmieniam parser MIDI w custom_nodes..."
docker compose exec comfyui-3d-artistic python3 -c '
import re

path = "/app/ComfyUI/custom_nodes/comfyui_ryanonyheinside/nodes/audio/midi_nodes.py"

with open(path, "r") as f:
    code = f.read()

new_class = """class MIDIToText:
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
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = (midi_number // 12) - 1
        name = notes[midi_number % 12]
        return f"{name}{octave}"

    def estimate_key(self, note_counts):
        """
        Uproszczony algorytm dopasowania profilu tonacji.
        Zwraca najbardziej prawdopodobną tonację (np. \"A minor\" lub \"C major\").
        """
        major_profile = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]
        minor_profile = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        
        best_fit_key = "C major"
        max_score = -1

        for root in range(12):
            major_score = sum(note_counts[(root + i) % 12] * major_profile[i] for i in range(12))
            if major_score > max_score:
                max_score = major_score
                best_fit_key = f"{note_names[root]} major"
            
            minor_score = sum(note_counts[(root + i) % 12] * minor_profile[i] for i in range(12))
            if minor_score > max_score:
                max_score = minor_score
                best_fit_key = f"{note_names[root]} minor"

        return best_fit_key

    def get_register_description(self, min_note, max_note):
        """Mapuje numery MIDI na opis fizycznego rejestru instrumentu."""
        desc = []
        if min_note < 48:
            desc.append("deep heavy bass notes")
        elif min_note < 60:
            desc.append("warm mid-low foundation")
        
        if max_note > 72:
            desc.append("bright, delicate high-register keys")
        elif max_note > 60:
            desc.append("clear mid-range melody")
            
        return " coupled with ".join(desc) if desc else "balanced mid-range frequencies"

    def translate_midi(self, midi, max_events):
        import mido
        
        bpm = 120
        for track in midi.tracks:
            for msg in track:
                if msg.type == "set_tempo":
                    bpm = int(mido.tempo2bpm(msg.tempo))
                    break

        raw_events = []
        note_counts = [0] * 12
        midi_numbers = []
        ticks_between_notes = []
        
        last_note_tick = None
        current_tick = 0
        
        for track in midi.tracks:
            current_tick = 0
            for msg in track:
                current_tick += msg.time
                if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
                    raw_events.append((current_tick, msg.note))
                    note_counts[msg.note % 12] += 1
                    midi_numbers.append(msg.note)
                    
                    if last_note_tick is not None:
                        ticks_between_notes.append(current_tick - last_note_tick)
                    last_note_tick = current_tick
        
        raw_events.sort(key=lambda x: x[0])

        if not raw_events:
            return ("MIDI Song Data: [No notes found in MIDI file]",)

        detected_key = self.estimate_key(note_counts)
        register_desc = self.get_register_description(min(midi_numbers), max(midi_numbers))

        avg_tick_diff = sum(ticks_between_notes) / len(ticks_between_notes) if ticks_between_notes else 0
        ticks_per_beat = midi.ticks_per_beat
        
        if avg_tick_diff == 0:
            rhythm_desc = "static sustained single-note performance"
        elif avg_tick_diff < (ticks_per_beat / 2):
            rhythm_desc = "fast, fluid, and flowing arpeggiated movement"
        elif avg_tick_diff < ticks_per_beat:
            rhythm_desc = "steady, moderate rhythmic cadence"
        else:
            rhythm_desc = "slow, spacious, heavily sustained and drifting progression"

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
                chord_str = f"[{' + '.join(current_chord)}]" if len(current_chord) > 1 else current_chord[0]
                if chord_str not in unique_chords:
                    unique_chords.append(chord_str)
                current_chord = [note]
                last_tick = tick
        
        current_chord = list(sorted(set(current_chord)))
        chord_str = f"[{" + ".join(current_chord)}]" if len(current_chord) > 1 else current_chord[0]
        if chord_str not in unique_chords:
            unique_chords.append(chord_str)

        featured_harmonies = ", ".join(unique_chords[:8])

        output_text = (
            f"MIDI Song Data:\\n"
            f"- Base Tempo: {bpm} BPM\\n"
            f"- Harmonic Key Profile: Written in the scale of {detected_key}\\n"
            f"- Sonic Range & Register: Spans from {register_desc}\\n"
            f"- Rhythmic Movement & Density: Characterized by a {rhythm_desc}\\n"
            f"- Primary Harmonic Structures: Features core harmonic shapes like {{{featured_harmonies}}}"
        )
        return (output_text,)"""

# Bezpieczna podmiana całej starej klasy na nową za pomocą regex
modified_code = re.sub(r"class MIDIToText:[\s\S]*?return\s*\(\s*output_text\s*,\s*\)", new_class, code)

with open(path, "w") as f:
    f.write(modified_code)

print(" -> Sukces: Parser MIDI został zaktualizowany o teorię muzyki!")
'

# 2. Hack promptu systemowego Qwena
echo "Krok 2/2: Podmieniam prompt systemowy w comfy_extras..."
docker compose exec comfyui-3d-artistic python3 -c '
import re

path = "/app/ComfyUI/comfy_extras/nodes_textgen.py"

with open(path, "r") as f:
    code = f.read()

new_prompt = """LTX2_T2V_SYSTEM_PROMPT = \"\"\"You are an expert Musicologist and Audio Synthesis Prompt Engineer. Your sole purpose is to translate the user input and the technical "MIDI Song Data" analysis into a single, cohesive, highly descriptive conditioning paragraph optimized for Stable Audio 3.

#### CRITICAL INSTRUCTIONS:
- Do NOT output raw technical lists or bullet points. You must blend all data into a natural, continuous prose.
- Integrate the "Harmonic Key Profile" (e.g., A minor) directly to define the emotional scale and tonal center.
- Use the "Sonic Range & Register" to describe the density and layout of the instruments (e.g., deep bass resonance vs high-register delicate keys).
- Translate the "Rhythmic Movement & Density" into clear performance style adjectives (e.g., flowing arpeggios, steady moderate cadence, drifting pads).
- Seamlessly embed the "Primary Harmonic Structures" (e.g., {[A2 + E3]}, {[F3 + C4]}) into your text to instruct the diffusion model on the core chord progressions and intervals to prioritize. Keep these specific chord brackets intact inside the text.
- Maintain the exact genre, style, mood, and instrumentation requested by the user.
- Output a single, dense, continuous paragraph in English. Avoid any meta-commentary, introductory remarks, headings, markdown, or structural summaries. Start directly with the musical description.\"\"\""""

modified_code = re.sub(r"LTX2_T2V_SYSTEM_PROMPT = \"\"\"[\s\S]*?\"\"\"", new_prompt, code)

with open(path, "w") as f:
    f.write(modified_code)

print(" -> Sukces: Prompt systemowy zaktualizowany!")
'

echo "=== WSZYSTKIE AKTUALIZACJE ZAKOŃCZONE POMYŚLNIE ==="
echo "Zrestartuj teraz kontener ComfyUI, aby wczytać nowe węzły."
