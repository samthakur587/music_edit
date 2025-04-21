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
        # Section variant code remains similar
        system_content = """You are a very experienced music producer and analyst. 
        You will be given audio stems and asked to create multiple variants of a specific section of a track.
        For each variant, return detailed instructions on how to arrange and process the stems.
        Be creative and make each variant sound distinct while maintaining a coherent musical style."""
        
        user_content = f"""I need 4 different variants for the {section_type} section of a track named "{song_name}".
        
        Available stems: {stems}
        
        BPM: {bpm}
        Bars: {bars}
        Section duration: {calculate_duration(bpm, bars)} seconds
        
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
                "description": "A brief description of this variant",
                "bpm": {bpm},
                "bars": {bars},
                "duration_seconds": {calculate_duration(bpm, bars)}
            }},
            "variant2": {{ ... }},
            "variant3": {{ ... }},
            "variant4": {{ ... }}
        }}
        """
    else:
        system_content = """You are an expert electronic music producer with deep knowledge of EDM track composition and arrangement. You understand how to create dynamic energy progression through different sections of a track and how to effectively use instruments, effects, and processing to create professional electronic music."""
        
        user_content = f"""I need professional production instructions for an EDM track named "{song_name}" using these available stems:
        {stems}

        Track parameters:
        - BPM: {bpm}
        - Variation level: p={p} (0=minimal variation, 1=maximum variation)

        Create a complete track with these sections in order:

        1. INTRO (8 bars, {calculate_duration(bpm, 8)} seconds):
           - Purpose: Establish the track's sonic identity and gradually introduce elements
           - Characteristics: Start minimal with primarily percussive elements, filtered versions of melodic elements
           - Typically includes: Kick drum, basic percussion, atmospheric sounds, filtered pads
           - Usually avoids: Bass drops, full chords, complete melodies

        2. BREAKDOWN1 (8 bars, {calculate_duration(bpm, 8)} seconds):
           - Purpose: Create a melodic foundation while reducing energy temporarily
           - Characteristics: Removal of kick drum, focus on harmony and melody, atmospheric elements
           - Typically includes: Pads, arpeggios, vocal samples, light percussion, subtle bass
           - Usually avoids: Heavy drums, aggressive basses, high-energy elements

        3. BUILDUP1 (8 bars, {calculate_duration(bpm, 8)} seconds):
           - Purpose: Create tension and anticipation before the drop
           - Characteristics: Gradually increasing energy, rising effects, drum intensification
           - Typically includes: Snare or clap rolls, rising effects, filter sweeps, pitch risers
           - Technical elements: Increasing highpass filter on master, automated white noise rises, volume automation

        4. DROP1 (16 bars, {calculate_duration(bpm, 16)} seconds):
           - Purpose: Release the built-up tension with maximum energy
           - Characteristics: Full rhythmic and sonic intensity, all main elements present
           - Typically includes: Heavy kick/bass combination, lead synths, full percussion, vocal hooks
           - Sound design: Sidechain compression on bass, heavy compression, wide stereo field

        5. BREAKDOWN2 (8 bars, {calculate_duration(bpm, 8)} seconds):
           - Purpose: Provide contrast and rest after the high-energy drop
           - Characteristics: Similar to first breakdown but with variations in melody/harmony
           - Typically includes: Elements from the drop but filtered, new melodic ideas, quieter dynamics

        6. BUILDUP2 (8 bars, {calculate_duration(bpm, 8)} seconds):
           - Purpose: Build tension again but with variation from first buildup
           - Characteristics: New tension-building techniques, different filter or effect automations
           - Should differ from BUILDUP1 by: Using different stems or processing them differently

        7. DROP2 (16 bars, {calculate_duration(bpm, 16)} seconds):
           - Purpose: Second climax with variations from the first drop
           - Characteristics: Same energy as first drop but with new elements or arrangements
           - How to vary: Add/remove stems, change processing, introduce new melodic elements

        8. OUTRO (8 bars, {calculate_duration(bpm, 8)} seconds):
           - Purpose: Gradually conclude the track for smooth DJ transitions
           - Characteristics: Gradual removal of elements, similar to intro but in reverse
           - Processing: Increasing filtering, fading out elements, subtle reverb tails

        The drops should utilize ALL available stems. Adjust the variation between sections according to p={p}.

        For each section, provide:
        1. Which stems to include
        2. Specific audio operations (filters, effects, automation)
        3. Arrangement instructions (when elements enter/exit)
        4. Transition techniques between sections

        Return your response as a properly formatted JSON object with this structure:
        {{
            "intro": {{
                "stems": ["stem1.wav", "stem2.wav"],
                "operations": [
                    {{"stem": "stem1.wav", "operation": "low_pass_filter", "value": 500}},
                    {{"stem": "stem2.wav", "operation": "fade_in", "value": 4000}}
                ],
                "arrangement": "Start with stem1 only, bring in stem2 at bar 5",
                "bpm": {bpm},
                "bars": 8,
                "duration_seconds": {calculate_duration(bpm, 8)},
                "transition_to_next": "Gradually filter in breakdown elements while removing kick"
            }},
            "breakdown1": {{ ... }},
            "buildup1": {{ ... }},
            "drop1": {{ ... }},
            "breakdown2": {{ ... }},
            "buildup2": {{ ... }},
            "drop2": {{ ... }},
            "outro": {{ ... }}
        }}
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
    
    # Get BPM and bars from section config
    bpm = section_config.get("bpm", 120)
    bars = section_config.get("bars", 16)
    target_duration_ms = int(calculate_duration(bpm, bars) * 1000)  # Convert to milliseconds
    
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
    
    # Create base audio
    if section_config.get("overlay", True) and final_stems:
        result = final_stems[0]
        for stem in final_stems[1:]:
            result = result.overlay(stem)
    elif final_stems:
        # Concatenate stems if not overlaying
        result = final_stems[0]
        for stem in final_stems[1:]:
            result += stem
    else:
        return AudioSegment.empty()
    
    # Adjust to target duration based on BPM and bars
    current_duration_ms = len(result)
    
    if current_duration_ms < target_duration_ms:
        # If too short, loop the audio until it reaches target duration
        repeats_needed = target_duration_ms // current_duration_ms
        remainder_ms = target_duration_ms % current_duration_ms
        
        extended_result = result * repeats_needed
        if remainder_ms > 0:
            extended_result += result[:remainder_ms]
        result = extended_result
    elif current_duration_ms > target_duration_ms:
        # If too long, trim to match target duration
        result = result[:target_duration_ms]
    
    print(f"Created section with duration: {len(result)/1000:.2f}s (target: {target_duration_ms/1000:.2f}s)")
    return result

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
            # Ensure BPM and bars are properly set in the variant config
            if "bpm" not in variant_config:
                variant_config["bpm"] = bpm
            if "bars" not in variant_config:
                variant_config["bars"] = bars
                
            audio = create_section_from_json(variant_config, audio_stems)
            description = variant_config.get("description", f"Variant {variant_key[-1]}")
            variants[variant_key] = {
                "audio": audio,
                "description": description,
                "config": variant_config
            }
    
    return variants

def create_full_track(stems_folder, llm_answer, bpm=120, crossfade_ms=500):
    """
    Create a full track with sections based on BPM and bar counts
    
    Args:
        stems_folder (str): Path to folder containing stem files
        llm_answer (dict): The full LLM response with section configurations
        bpm (int): Default BPM if not specified in sections
        crossfade_ms (int): Crossfade duration in milliseconds
        
    Returns:
        AudioSegment: The final track
    """
    final_track = None
    
    # Load stems
    stems = load_audio_files(stems_folder)
    
    # Define the order of sections and their creation functions
    sections = [
        ("intro", create_intro),
        ("breakdown1", create_breakdown1),
        ("buildup1", create_buildup1),
        ("drop1", create_drop1),
        ("breakdown2", create_breakdown2),
        ("buildup2", create_buildup2),
        ("drop2", create_drop2),
        ("outro", create_outro)
    ]
    
    # Process each section in order
    section_durations = {}
    for section_name, create_function in sections:
        section_key = f"create_{section_name}"
        if section_key not in llm_answer:
            print(f"Skipping section {section_name} (not found in LLM answer)")
            continue
            
        # Get section config and ensure BPM and bars are set
        section_config = llm_answer[section_key]
        if not section_config:
            continue
            
        # Update section config with BPM and bars if not present
        if "bpm" not in section_config:
            section_config["bpm"] = bpm
        if "bars" not in section_config:
            # Default to 16 bars for most sections, 8 for intro/outro
            default_bars = 8 if section_name in ["intro", "outro"] else 16
            section_config["bars"] = default_bars
        
        # Print section details
        section_bpm = section_config["bpm"]
        section_bars = section_config["bars"]
        section_duration = calculate_duration(section_bpm, section_bars)
        section_durations[section_name] = section_duration
        
        print(f"\nCreating {section_name}:")
        print(f"  - BPM: {section_bpm}")
        print(f"  - Bars: {section_bars}")
        print(f"  - Target duration: {get_formatted_duration(section_duration)}")
        
        # Create audio for this section
        section_audio = create_function(llm_answer, stems)
        
        # Add to final track
        if final_track is None:
            final_track = section_audio
        else:
            final_track = final_track.append(section_audio, crossfade=crossfade_ms)
    
    # Print summary of section durations
    print("\nSection durations:")
    total_duration = sum(section_durations.values())
    for section, duration in section_durations.items():
        print(f"  - {section}: {get_formatted_duration(duration)} ({duration:.1f}s)")
    print(f"Total track duration: {get_formatted_duration(total_duration)} ({total_duration:.1f}s)")
    
    return final_track

def create_intro(llm_answer, stems):
    """Create intro section from LLM answer with proper duration"""
    section_config = llm_answer.get("create_intro", {})
    return create_section_from_json(section_config, stems)

def create_breakdown1(llm_answer, stems):
    """Create breakdown1 section from LLM answer with proper duration"""
    section_config = llm_answer.get("create_breakdown1", {})
    return create_section_from_json(section_config, stems)

def create_buildup1(llm_answer, stems):
    """Create buildup1 section from LLM answer with proper duration"""
    section_config = llm_answer.get("create_buildup1", {})
    return create_section_from_json(section_config, stems)

def create_drop1(llm_answer, stems):
    """Create drop1 section from LLM answer with proper duration"""
    section_config = llm_answer.get("create_drop1", {})
    return create_section_from_json(section_config, stems)

def create_breakdown2(llm_answer, stems):
    """Create breakdown2 section from LLM answer with proper duration"""
    section_config = llm_answer.get("create_breakdown2", {})
    return create_section_from_json(section_config, stems)

def create_buildup2(llm_answer, stems):
    """Create buildup2 section from LLM answer with proper duration"""
    section_config = llm_answer.get("create_buildup2", {})
    return create_section_from_json(section_config, stems)

def create_drop2(llm_answer, stems):
    """Create drop2 section from LLM answer with proper duration"""
    section_config = llm_answer.get("create_drop2", {})
    return create_section_from_json(section_config, stems)

def create_outro(llm_answer, stems):
    """Create outro section from LLM answer with proper duration"""
    section_config = llm_answer.get("create_outro", {})
    return create_section_from_json(section_config, stems)

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

# def main(stems_folder, output_folder, song_name="New Track", bpm=120, variation_level=0.5):
#     """
#     Main function to create a full track with proper BPM-based timing
    
#     Args:
#         stems_folder (str): Path to folder containing stem files
#         output_folder (str): Path to output folder for generated audio
#         song_name (str): Name of the song
#         bpm (int): Beats per minute
#         variation_level (float): Variation parameter (0-1)
#     """
#     # Ensure output folder exists
#     if not os.path.exists(output_folder):
#         os.makedirs(output_folder)
    
#     # Get stems and rename files to remove spaces
#     rename_files_remove_spaces(stems_folder)
#     stems = get_stems(stems_folder)
    
#     # Define default bar counts for each section
#     section_bars = {
#         "intro": 8,
#         "breakdown1": 16,
#         "buildup1": 16,
#         "drop1": 16,
#         "breakdown2": 16,
#         "outro": 8
#     }
    
#     # Generate full track arrangement from LLM
#     llm_response = make_groq_call(
#         stems, 
#         song_name, 
#         variation_level, 
#         section_type=None, 
#         bpm=bpm, 
#         bars=16  # Default bars for main loop
#     )
    
#     # Update section configs with proper BPM and bar counts
#     for section_name in section_bars:
#         section_key = f"create_{section_name}"
#         if section_key in llm_response and llm_response[section_key]:
#             llm_response[section_key]["bpm"] = bpm
#             llm_response[section_key]["bars"] = section_bars[section_name]
#             duration = calculate_duration(bpm, section_bars[section_name])
#             llm_response[section_key]["duration_seconds"] = duration
    
#     # Create full track with proper timing
#     full_track = create_full_track(stems_folder, llm_response, bpm=bpm)
    
#     # Export full track
#     output_path = os.path.join(output_folder, f"{song_name}.wav")
#     full_track.export(output_path, format="wav")
#     print(f"Full track exported to: {output_path}")
    
#     # Return stats
#     total_duration = sum(calculate_duration(bpm, section_bars[section]) 
#                          for section in section_bars)
    
#     return {
#         "song_name": song_name,
#         "bpm": bpm,
#         "total_bars": sum(section_bars.values()),
#         "duration": get_formatted_duration(total_duration),
#         "output_path": output_path
#     }

# # Example usage
# if __name__ == "__main__":
#     # Example parameters - these would come from user input in a real application
#     stems_folder = "./stems"
#     output_folder = "./output"
#     song_name = "Groovy Beat"
#     bpm = 128
#     variation_level = 0.7
    
#     # Generate track
#     result = main(stems_folder, output_folder, song_name, bpm, variation_level)
    
#     # Print result
#     print("\nTrack generation complete!")
#     print(f"Song: {result['song_name']}")
#     print(f"BPM: {result['bpm']}")
#     print(f"Total bars: {result['total_bars']}")
#     print(f"Duration: {result['duration']}")
#     print(f"Output file: {result['output_path']}")