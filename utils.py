import os
import shutil
import json
import tempfile
from pydub import AudioSegment
from pydub.effects import low_pass_filter, high_pass_filter
from tqdm import tqdm
from groq import Groq
from dotenv import load_dotenv
import random

load_dotenv()

def make_groq_call(stems, song_name, p, section_type=None, bpm=120, bars=16):
    """
    Make a call to the Groq API to get music production instructions.
    
    Args:
        stems (list): List of available stem files
        song_name (str): Name of the song
        p (float): Variation parameter (0-1)
        section_type (str, optional): Specific section to generate variants for
        bpm (int): Beats per minute
        bars (int): Number of bars
        
    Returns:
        dict: JSON response with production instructions
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # Customize prompt based on whether we're generating a full track or section variants
    if section_type:
        system_content = """You are a very experienced music producer and analyst. 
        You will be given audio stems and asked to create multiple variants of a specific section of a track.
        For each variant, return detailed instructions on how to arrange and process the stems.
        Be creative and make each variant sound distinct while maintaining a coherent musical style."""
        
        user_content = f"""I need 4 different variants for the {section_type} section of a track named "{song_name}".
        
        Available stems: {stems}
        
        BPM: {bpm}
        Bars: {bars}
        
        For each variant, please provide specific instructions on:
        1. Which stems to include
        2. What audio operations to apply (filters, fades, etc.)
        3. How the stems should be arranged
        
        Make the variants diverse but coherent, with variation level p={p} (0=minimal variation, 1=maximum variation).
        
        Return your response as a JSON object with this structure:
        {{
            "variant1": {{
                "stems": ["stem1.wav", "stem2.wav"],
                "operations": [
                    {{"stem": "stem1.wav", "operation": "low_pass_filter", "value": 500}},
                    {{"stem": "stem2.wav", "operation": "fade_in", "value": 1000}}
                ],
                "overlay": true,
                "description": "A brief description of this variant"
            }},
            "variant2": {{ ... }},
            "variant3": {{ ... }},
            "variant4": {{ ... }}
        }}
        """
    else:
        system_content = """You are a very experienced music producer and analyst. For a given audio folder, that has the instruments, are combined to make a loop, and make some variations of it as well. After analyzing the code, you are supposed to return the code containing the different functions for producing the full track."""
        
        user_content = f"""Now, you have a new song {song_name}, which has the following contents:
        {stems}
        
        BPM: {bpm}
        Bars: {bars}
        
        Return the code as per discussed in example. Make proper arrangements, for best groovy music. Create 3 variations and return code in JSON. And make sure to use as many instruments possible in each variation.
        
        NOTE: And at least once, the MAIN loop should have ALL stems.
        
        Like the variations should be like the main full loop, with some adjustments according to value of p={p} (p will remain in between 0-1; 0 means no variation in loop and 1 means high variation in loop), and then another variation can be a two times repeat of the full loop, with some effects in second time. Make intro better, with some more instruments.
        
        The main loop should have ALL wav files, don't exclude any please. Return proper JSON, with all the keys and values.
        """
    
    completion = client.chat.completions.create(
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ],
        temperature=1,
        top_p=1,
        stream=False,
        response_format={"type": "json_object"},
        stop=None,
    )

    return json.loads(completion.choices[0].message.content)

def rename_files_remove_spaces(folder):
    """Rename all files in the folder by removing spaces from filenames"""
    files_renamed = 0
    for file in os.listdir(folder):
        if ' ' in file:
            old_path = os.path.join(folder, file)
            new_file = file.replace(' ', '')
            new_path = os.path.join(folder, new_file)
            
            # Only rename if the new file doesn't already exist
            if not os.path.exists(new_path):
                os.rename(old_path, new_path)
                print(f"Renamed: {file} → {new_file}")
                files_renamed += 1
    
    print(f"Total files renamed: {files_renamed}")

def load_audio_files(folder):
    """Load all WAV files from a folder into memory"""
    files = sorted([f for f in os.listdir(folder) if f.endswith(".wav")])
    stems = {}
    for file in tqdm(files, desc="Loading audio files"):
        path = os.path.join(folder, file)
        audio = AudioSegment.from_wav(path)
        stems[file] = audio
    return stems

def get_stems(folder):
    """Get a list of all WAV files in a folder"""
    files = sorted([f for f in os.listdir(folder) if f.endswith(".wav")])
    return files

def apply_audio_operation(audio, operation, value):
    """Apply various audio operations to an AudioSegment"""
    if operation == "low_pass_filter":
        return low_pass_filter(audio, value)
    elif operation == "high_pass_filter":
        return high_pass_filter(audio, value)
    elif operation == "fade_in":
        return audio.fade_in(value)
    elif operation == "fade_out":
        return audio.fade_out(value)
    elif operation == "reverb":
        # Simple reverb simulation by adding delayed and attenuated copies
        result = audio
        for delay in [50, 100, 150, 200]:
            attenuated = audio - (value * 10)  # Reduce volume based on reverb value
            delayed = AudioSegment.silent(duration=delay) + attenuated
            result = result.overlay(delayed)
        return result
    elif operation == "delay":
        # Simulate delay by adding a delayed copy
        result = audio
        delayed = AudioSegment.silent(duration=value) + (audio - 6)  # -6dB for the echo
        return result.overlay(delayed)
    elif operation == "distortion":
        # Simulate distortion by adding some limiting/clipping
        gain = 1.0 + (value * 5)  # Boost the gain based on distortion value
        return audio + (gain)  # Add gain in dB
    elif operation == "pitch_shift":
        # Note: pydub doesn't natively support pitch shifting
        print(f"Warning: Pitch shift not implemented, value: {value}")
        return audio
    elif operation == "volume":
        # Adjust volume by dB
        return audio + value
    return audio

def create_section_from_json(section_config, stems):
    """Create an audio section based on JSON configuration"""
    if not section_config:
        print("No configuration found for section")
        return AudioSegment.empty()
    
    section_stems = []
    for stem_name in section_config["stems"]:
        # First try the original stem name
        if stem_name in stems:
            section_stems.append(stems[stem_name])
        else:
            # Try the name without spaces
            no_spaces_name = stem_name.replace(' ', '')
            if no_spaces_name in stems:
                section_stems.append(stems[no_spaces_name])
            else:
                print(f"Warning: Stem {stem_name} not found (with or without spaces)")
    
    # Apply operations to stems
    processed_stems = {name: audio for name, audio in stems.items()}
    for op in section_config.get("operations", []):
        stem_name = op["stem"]
        operation = op["operation"]
        value = op["value"]
        
        # Check both original and no-spaces versions
        stem_key = None
        if stem_name in processed_stems:
            stem_key = stem_name
        else:
            no_spaces_name = stem_name.replace(' ', '')
            if no_spaces_name in processed_stems:
                stem_key = no_spaces_name
        
        if stem_key and operation != "overlay":
            processed_stems[stem_key] = apply_audio_operation(processed_stems[stem_key], operation, value)
    
    # Collect the processed stems for this section
    final_stems = []
    for stem_name in section_config["stems"]:
        if stem_name in processed_stems:
            final_stems.append(processed_stems[stem_name])
        else:
            no_spaces_name = stem_name.replace(' ', '')
            if no_spaces_name in processed_stems:
                final_stems.append(processed_stems[no_spaces_name])
    
    # Overlay stems if specified
    if section_config.get("overlay", True) and final_stems:
        result = final_stems[0]
        for stem in final_stems[1:]:
            result = result.overlay(stem)
        return result
    elif final_stems:
        # Concatenate stems if not overlaying
        result = final_stems[0]
        for stem in final_stems[1:]:
            result += stem
        return result
    
    return AudioSegment.empty()

def generate_section_variants(stems_folder, section_type, bpm, bars, p=0.5):
    """
    Generate multiple variants for a specific section
    
    Args:
        stems_folder (str): Path to folder containing stem files
        section_type (str): Type of section (intro, verse, chorus, etc.)
        bpm (int): Beats per minute
        bars (int): Number of bars
        p (float): Variation parameter (0-1)
        
    Returns:
        dict: Dictionary of variant audio segments and their descriptions
    """
    stems = get_stems(stems_folder)
    llm_response = make_groq_call(stems, f"{section_type} section", p, section_type=section_type, bpm=bpm, bars=bars)
    
    # Load audio files
    audio_stems = load_audio_files(stems_folder)
    if not audio_stems:
        print("No stems loaded.")
        return {}
    
    # Create each variant
    variants = {}
    for variant_key in llm_response:
        if variant_key.startswith("variant"):
            variant_config = llm_response[variant_key]
            audio = create_section_from_json(variant_config, audio_stems)
            description = variant_config.get("description", f"Variant {variant_key[-1]}")
            variants[variant_key] = {
                "audio": audio,
                "description": description,
                "config": variant_config
            }
    
    return variants

def create_full_track(sections_folder, selected_variants, crossfade_ms=500):
    """
    Create a full track from selected variants
    
    Args:
        sections_folder (dict): Dict mapping section names to their folder paths
        selected_variants (dict): Dict mapping section names to their selected variant configs
        crossfade_ms (int): Crossfade duration in milliseconds
        
    Returns:
        AudioSegment: The final track
    """
    final_track = None
    
    # Define the order of sections
    section_order = ["intro", "variation1", "full_loop", "variation2", "variation3", "outro"]
    
    # Process each section in order
    for section_name in section_order:
        if section_name not in selected_variants:
            continue
            
        # Load stems for this section
        stems = load_audio_files(sections_folder)
        
        # Get the selected variant config
        variant_config = selected_variants[section_name]
        
        # Create audio for this section
        section_audio = create_section_from_json(variant_config, stems)
        
        # Add to final track
        if final_track is None:
            final_track = section_audio
        else:
            final_track = final_track.append(section_audio, crossfade=crossfade_ms)
    
    return final_track

def create_intro(llm_answer, stems):
    """Create intro section from LLM answer"""
    return create_section_from_json(llm_answer.get("create_intro", {}), stems)

def create_variation1(llm_answer, stems):
    """Create variation1 section from LLM answer"""
    return create_section_from_json(llm_answer.get("create_variation1", {}), stems)

def create_full_loop(llm_answer, stems):
    """Create full loop section from LLM answer"""
    return create_section_from_json(llm_answer.get("create_full_loop", {}), stems)

def create_variation2(llm_answer, stems):
    """Create variation2 section from LLM answer"""
    return create_section_from_json(llm_answer.get("create_variation2", {}), stems)

def create_variation3(llm_answer, stems):
    """Create variation3 section from LLM answer"""
    return create_section_from_json(llm_answer.get("create_variation3", {}), stems)

def create_outro(llm_answer, stems):
    """Create outro section from LLM answer"""
    return create_section_from_json(llm_answer.get("create_outro", {}), stems)

def calculate_duration(bpm, bars):
    """Calculate duration in seconds for a given BPM and number of bars"""
    # Assuming 4/4 time signature (4 beats per bar)
    beats_per_bar = 4
    duration_seconds = (bars * beats_per_bar * 60) / bpm
    return duration_seconds

def get_formatted_duration(seconds):
    """Format duration in seconds to MM:SS format"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes}:{seconds:02d}"

def export_section_variants(variants, output_folder, section_name):
    """Export section variants to audio files"""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    file_paths = {}
    for variant_key, variant_data in variants.items():
        output_path = os.path.join(output_folder, f"{section_name}_{variant_key}.wav")
        variant_data["audio"].export(output_path, format="wav")
        file_paths[variant_key] = output_path
        
    return file_paths