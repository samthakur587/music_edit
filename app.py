import os
import gradio as gr
import json
import shutil
import tempfile
from pathlib import Path
import numpy as np
from utils import (
    rename_files_remove_spaces,
    load_audio_files,
    get_stems,
    generate_section_variants,
    export_section_variants
)

# Global variable to store the temporary directory
TEMP_DIR = None
# Global variable to store the selected variants
SELECTED_VARIANTS = {}
# Global variable to store all variants for each section
ALL_VARIANTS = {}
# Global variable to store the uploaded stems
UPLOADED_STEMS = {}

def process_uploaded_files(files, progress=gr.Progress()):
    """Process uploaded files and return basic info"""
    global TEMP_DIR, UPLOADED_STEMS
    
    try:
        if not files:
            return "Error: No files uploaded", []
            
        progress(0, desc="Starting process...")
        
        # Create a temporary directory for processing
        TEMP_DIR = tempfile.mkdtemp()
        try:
            # Copy uploaded files to temp directory
            progress(0.2, desc="Copying uploaded files...")
            for file in files:
                if file.name.lower().endswith('.wav'):
                    shutil.copy2(file.name, TEMP_DIR)
            
            # First rename all files to remove spaces
            progress(0.5, desc="Renaming files...")
            rename_files_remove_spaces(TEMP_DIR)
            
            # Load audio files
            progress(0.8, desc="Loading audio files...")
            UPLOADED_STEMS = load_audio_files(TEMP_DIR)
            if not UPLOADED_STEMS:
                return "Error: No stems loaded", []
            
            # Get stem names
            stem_names = get_stems(TEMP_DIR)
            
            progress(1.0, desc="Complete!")
            return f"Successfully loaded {len(stem_names)} stems", stem_names
            
        except Exception as e:
            if os.path.exists(TEMP_DIR):
                shutil.rmtree(TEMP_DIR)
            TEMP_DIR = None
            raise e
        
    except Exception as e:
        return f"Error occurred: {str(e)}", []

def generate_section_variants_handler(
    section_type, 
    bpm_value, 
    bars_value, 
    p_value,
    progress=gr.Progress()
):
    """Handler function for generating section variants"""
    global TEMP_DIR, ALL_VARIANTS
    
    if not TEMP_DIR or not os.path.exists(TEMP_DIR):
        return "Error: No stems loaded. Please upload stems first.", None, None, None, None
    
    try:
        progress(0.1, desc=f"Generating {section_type} variants...")
        
        # Generate variants
        variants = generate_section_variants(
            TEMP_DIR, 
            section_type, 
            bpm=int(bpm_value), 
            bars=int(bars_value), 
            p=float(p_value)
        )
        
        # Store variants for later use
        ALL_VARIANTS[section_type] = variants
        
        progress(0.6, desc="Exporting audio files...")
        
        # Export variants to audio files
        variant_output_dir = os.path.join(TEMP_DIR, section_type + "_variants")
        audio_paths = export_section_variants(variants, variant_output_dir, section_type)
        
        # Create audio elements for each variant
        variant1_audio = audio_paths.get("variant1")
        variant2_audio = audio_paths.get("variant2")
        variant3_audio = audio_paths.get("variant3")
        variant4_audio = audio_paths.get("variant4")
        
        # Descriptions
        descriptions = {
            key: data["description"] 
            for key, data in variants.items()
        }
        descriptions_json = json.dumps(descriptions, indent=2)
        
        progress(1.0, desc="Complete!")
        
        return (
            f"Generated {len(variants)} variants for {section_type}",
            variant1_audio,
            variant2_audio,
            variant3_audio,
            variant4_audio,
            descriptions_json
        )
        
    except Exception as e:
        return f"Error generating variants: {str(e)}", None, None, None, None, None

def select_variant(section_type, variant_num):
    """Select a variant for a specific section"""
    global ALL_VARIANTS, SELECTED_VARIANTS
    
    if section_type not in ALL_VARIANTS:
        return f"No variants generated for {section_type} yet"
    
    variant_key = f"variant{variant_num}"
    if variant_key not in ALL_VARIANTS[section_type]:
        return f"Variant {variant_num} not found for {section_type}"
    
    # Store the selected variant config
    SELECTED_VARIANTS[section_type] = ALL_VARIANTS[section_type][variant_key]["config"]
    
    return f"Selected variant {variant_num} for {section_type}"

def generate_full_track(
    crossfade_ms,
    output_track_name,
    include_intro,
    include_breakdown1,
    include_drop1,
    include_breakdown2,
    include_drop2,
    include_outro,
    progress=gr.Progress()
):
    """Generate the full track from selected variants"""
    global TEMP_DIR, SELECTED_VARIANTS, UPLOADED_STEMS
    
    if not TEMP_DIR or not os.path.exists(TEMP_DIR):
        return "Error: No stems loaded", None, None
    
    try:
        progress(0.1, desc="Preparing to generate full track...")
        
        # Check which sections to include based on user selections and available variants
        sections_to_include = {}
        
        if include_intro and "intro" in SELECTED_VARIANTS:
            sections_to_include["intro"] = SELECTED_VARIANTS["intro"]
            
        if include_breakdown1 and "breakdown1" in SELECTED_VARIANTS:
            sections_to_include["breakdown1"] = SELECTED_VARIANTS["breakdown1"]
            
        # We always include the buildup 1 if it exists
        if "buildup1" in SELECTED_VARIANTS:
            sections_to_include["buildup1"] = SELECTED_VARIANTS["buildup1"]
            
        if include_drop1 and "drop1" in SELECTED_VARIANTS:
            sections_to_include["drop1"] = SELECTED_VARIANTS["drop1"]
            
        if include_breakdown2 and "breakdown2" in SELECTED_VARIANTS:
            sections_to_include["breakdown2"] = SELECTED_VARIANTS["breakdown2"]
        
        if "buildup2" in SELECTED_VARIANTS:
            sections_to_include["buildup2"] = SELECTED_VARIANTS["buildup2"]
        if include_drop2 and "drop2" in SELECTED_VARIANTS:
            sections_to_include["drop2"] = SELECTED_VARIANTS["drop2"]
        
        if include_outro and "outro" in SELECTED_VARIANTS:
            sections_to_include["outro"] = SELECTED_VARIANTS["outro"]
        
        if not sections_to_include:
            return "Error: No sections selected or available", None, None
        
        progress(0.3, desc="Creating track structure...")
        
        # Create the final track
        final_track = None
        
        # Define the order of sections
        section_order = ["intro", "breakdown1", "buildup1", "drop1", "breakdown2", "buildup2", "drop2" "outro"]
        
        # Process each section in order
        for section_name in section_order:
            if section_name not in sections_to_include:
                continue
                
            progress(0.4 + 0.1*section_order.index(section_name)/len(section_order), 
                     desc=f"Processing {section_name}...")
            
            # Get the selected variant config
            variant_config = sections_to_include[section_name]
            
            # Create temporary copy of stems to avoid modifying the originals
            stems_copy = {k: v for k, v in UPLOADED_STEMS.items()}
            
            # Create audio for this section
            from utils import create_section_from_json
            section_audio = create_section_from_json(variant_config, stems_copy)
            
            # Add to final track
            if final_track is None:
                final_track = section_audio
            else:
                final_track = final_track.append(section_audio, crossfade=crossfade_ms)
        
        progress(0.9, desc="Exporting final track...")
        
        # Export the final track
        full_track_path = os.path.join(TEMP_DIR, output_track_name)
        final_track.export(full_track_path, format="wav")
        
        # Create track summary
        sections_list = list(sections_to_include.keys())
        track_duration = len(final_track) / 1000  # in seconds
        
        track_summary = {
            "Sections included": sections_list,
            "Total sections": len(sections_list),
            "Duration": f"{int(track_duration // 60)}:{int(track_duration % 60):02d}",
            "Crossfade": f"{crossfade_ms} ms"
        }
        
        progress(1.0, desc="Complete!")
        
        return "Track generated successfully!", full_track_path, json.dumps(track_summary, indent=2)
        
    except Exception as e:
        return f"Error generating track: {str(e)}", None, None

def generate_buildup1_variants(
    bpm_value, 
    bars_value, 
    p_value,
    progress=gr.Progress()
):
    """Generate variants for the buildup 1 section"""
    return generate_section_variants_handler(
        "buildup1", 
        bpm_value, 
        bars_value, 
        p_value,
        progress
    )

def generate_buildup2_variants(
    bpm_value, 
    bars_value, 
    p_value,
    progress=gr.Progress()
):
    """Generate variants for the buildup 2 section"""
    return generate_section_variants_handler(
        "buildup2", 
        bpm_value, 
        bars_value, 
        p_value,
        progress
    )


# Create Gradio interface
with gr.Blocks(title="Interactive Music Track Generator") as demo:
    gr.Markdown("# Interactive Music Track Generator")
    gr.Markdown("Upload your WAV stems, generate variants for each section, and create a full track")
    
    # Global variables for UI state
    stem_list = gr.State([])
    
    with gr.Tab("1. Upload Stems"):
        with gr.Row():
            with gr.Column():
                # File upload section
                gr.Markdown("### Upload Files")
                gr.Markdown("Drag and drop your WAV stem files here")
                file_input = gr.File(
                    label="WAV Stems",
                    file_count="multiple",
                    file_types=[".wav"]
                )
                
                upload_btn = gr.Button("Upload and Process Files", variant="primary")
                
            with gr.Column():
                upload_status = gr.Textbox(label="Upload Status", interactive=False)
                stem_display = gr.JSON(label="Available Stems")
    
    with gr.Tab("2. Generate Section Variants"):
        with gr.Accordion("Generate buildup 1 Variants", open=True):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### buildup 1 Parameters")
                    buildup1_bpm = gr.Slider(
                        label="BPM (Beats Per Minute)",
                        minimum=60,
                        maximum=180,
                        value=120,
                        step=1
                    )
                    buildup1_bars = gr.Slider(
                        label="Number of Bars",
                        minimum=4,
                        maximum=64,
                        value=16,
                        step=4
                    )
                    buildup1_p = gr.Slider(
                        label="Variation Parameter (p)",
                        minimum=0,
                        maximum=1,
                        value=0.5,
                        step=0.1
                    )
                    
                    generate_buildup1_btn = gr.Button("Generate buildup 1 Variants", variant="primary")
                    
                with gr.Column(scale=2):
                    buildup1_status = gr.Textbox(label="Status", interactive=False)
                    buildup1_descriptions = gr.JSON(label="Variant Descriptions")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 1")
                    buildup1_variant1 = gr.Audio(label="Variant 1")
                    select_buildup1_1_btn = gr.Button("Select Variant 1")
                with gr.Column():
                    gr.Markdown("### Variant 2")
                    buildup1_variant2 = gr.Audio(label="Variant 2")
                    select_buildup1_2_btn = gr.Button("Select Variant 2")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 3")
                    buildup1_variant3 = gr.Audio(label="Variant 3")
                    select_buildup1_3_btn = gr.Button("Select Variant 3")
                with gr.Column():
                    gr.Markdown("### Variant 4")
                    buildup1_variant4 = gr.Audio(label="Variant 4")
                    select_buildup1_4_btn = gr.Button("Select Variant 4")
        
        with gr.Accordion("Generate Intro Variants"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Intro Parameters")
                    intro_bpm = gr.Slider(
                        label="BPM (Beats Per Minute)",
                        minimum=60,
                        maximum=180,
                        value=120,
                        step=1
                    )
                    intro_bars = gr.Slider(
                        label="Number of Bars",
                        minimum=4,
                        maximum=64,
                        value=8,
                        step=4
                    )
                    intro_p = gr.Slider(
                        label="Variation Parameter (p)",
                        minimum=0,
                        maximum=1,
                        value=0.3,
                        step=0.1
                    )
                    
                    generate_intro_btn = gr.Button("Generate Intro Variants", variant="primary")
                    
                with gr.Column(scale=2):
                    intro_status = gr.Textbox(label="Status", interactive=False)
                    intro_descriptions = gr.JSON(label="Variant Descriptions")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 1")
                    intro_variant1 = gr.Audio(label="Variant 1")
                    select_intro_1_btn = gr.Button("Select Variant 1")
                with gr.Column():
                    gr.Markdown("### Variant 2")
                    intro_variant2 = gr.Audio(label="Variant 2")
                    select_intro_2_btn = gr.Button("Select Variant 2")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 3")
                    intro_variant3 = gr.Audio(label="Variant 3")
                    select_intro_3_btn = gr.Button("Select Variant 3")
                with gr.Column():
                    gr.Markdown("### Variant 4")
                    intro_variant4 = gr.Audio(label="Variant 4")
                    select_intro_4_btn = gr.Button("Select Variant 4")
        
        with gr.Accordion("Generate breakdown 1 Variants"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### breakdown 1 Parameters")
                    var1_bpm = gr.Slider(
                        label="BPM (Beats Per Minute)",
                        minimum=60,
                        maximum=180,
                        value=120,
                        step=1
                    )
                    var1_bars = gr.Slider(
                        label="Number of Bars",
                        minimum=4,
                        maximum=64,
                        value=16,
                        step=4
                    )
                    var1_p = gr.Slider(
                        label="Variation Parameter (p)",
                        minimum=0,
                        maximum=1,
                        value=0.4,
                        step=0.1
                    )
                    generate_var1_btn = gr.Button("Generate breakdown 1 Variants", variant="primary")
                    
                with gr.Column(scale=2):
                    var1_status = gr.Textbox(label="Status", interactive=False)
                    var1_descriptions = gr.JSON(label="Variant Descriptions")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 1")
                    var1_variant1 = gr.Audio(label="Variant 1")
                    select_var1_1_btn = gr.Button("Select Variant 1")
                with gr.Column():
                    gr.Markdown("### Variant 2")
                    var1_variant2 = gr.Audio(label="Variant 2")
                    select_var1_2_btn = gr.Button("Select Variant 2")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 3")
                    var1_variant3 = gr.Audio(label="Variant 3")
                    select_var1_3_btn = gr.Button("Select Variant 3")
                with gr.Column():
                    gr.Markdown("### Variant 4")
                    var1_variant4 = gr.Audio(label="Variant 4")
                    select_var1_4_btn = gr.Button("Select Variant 4")
        
        with gr.Accordion("Generate drop 1 Variants"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### drop 1 Parameters")
                    var2_bpm = gr.Slider(
                        label="BPM (Beats Per Minute)",
                        minimum=60,
                        maximum=180,
                        value=120,
                        step=1
                    )
                    var2_bars = gr.Slider(
                        label="Number of Bars",
                        minimum=4,
                        maximum=64,
                        value=16,
                        step=4
                    )
                    var2_p = gr.Slider(
                        label="Variation Parameter (p)",
                        minimum=0,
                        maximum=1,
                        value=0.6,
                        step=0.1
                    )
                    
                    generate_var2_btn = gr.Button("Generate drop 1 Variants", variant="primary")
                    
                with gr.Column(scale=2):
                    var2_status = gr.Textbox(label="Status", interactive=False)
                    var2_descriptions = gr.JSON(label="Variant Descriptions")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 1")
                    var2_variant1 = gr.Audio(label="Variant 1")
                    select_var2_1_btn = gr.Button("Select Variant 1")
                with gr.Column():
                    gr.Markdown("### Variant 2")
                    var2_variant2 = gr.Audio(label="Variant 2")
                    select_var2_2_btn = gr.Button("Select Variant 2")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 3")
                    var2_variant3 = gr.Audio(label="Variant 3")
                    select_var2_3_btn = gr.Button("Select Variant 3")
                with gr.Column():
                    gr.Markdown("### Variant 4")
                    var2_variant4 = gr.Audio(label="Variant 4")
                    select_var2_4_btn = gr.Button("Select Variant 4")
                    
        with gr.Accordion("Generate breakdown 2 Variants"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### breakdown 2 Parameters")
                    var3_bpm = gr.Slider(
                        label="BPM (Beats Per Minute)",
                        minimum=60,
                        maximum=180,
                        value=120,
                        step=1
                    )
                    var3_bars = gr.Slider(
                        label="Number of Bars",
                        minimum=4,
                        maximum=64,
                        value=16,
                        step=4
                    )
                    var3_p = gr.Slider(
                        label="Variation Parameter (p)",
                        minimum=0,
                        maximum=1,
                        value=0.7,
                        step=0.1
                    )
                    
                    generate_var3_btn = gr.Button("Generate breakdown 2 Variants", variant="primary")
                    
                with gr.Column(scale=2):
                    var3_status = gr.Textbox(label="Status", interactive=False)
                    var3_descriptions = gr.JSON(label="Variant Descriptions")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 1")
                    var3_variant1 = gr.Audio(label="Variant 1")
                    select_var3_1_btn = gr.Button("Select Variant 1")
                with gr.Column():
                    gr.Markdown("### Variant 2")
                    var3_variant2 = gr.Audio(label="Variant 2")
                    select_var3_2_btn = gr.Button("Select Variant 2")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 3")
                    var3_variant3 = gr.Audio(label="Variant 3")
                    select_var3_3_btn = gr.Button("Select Variant 3")
                with gr.Column():
                    gr.Markdown("### Variant 4")
                    var3_variant4 = gr.Audio(label="Variant 4")
                    select_var3_4_btn = gr.Button("Select Variant 4")
        

        with gr.Accordion("Generate buildup 2 Variants", open=True):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### buildup 1 Parameters")
                    buildup2_bpm = gr.Slider(
                        label="BPM (Beats Per Minute)",
                        minimum=60,
                        maximum=180,
                        value=120,
                        step=1
                    )
                    buildup2_bars = gr.Slider(
                        label="Number of Bars",
                        minimum=4,
                        maximum=64,
                        value=16,
                        step=4
                    )
                    buildup2_p = gr.Slider(
                        label="Variation Parameter (p)",
                        minimum=0,
                        maximum=1,
                        value=0.5,
                        step=0.1
                    )
                    
                    generate_buildup2_btn = gr.Button("Generate buildup 1 Variants", variant="primary")
                    
                with gr.Column(scale=2):
                    buildup2_status = gr.Textbox(label="Status", interactive=False)
                    buildup2_descriptions = gr.JSON(label="Variant Descriptions")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 1")
                    buildup2_variant1 = gr.Audio(label="Variant 1")
                    select_buildup2_1_btn = gr.Button("Select Variant 1")
                with gr.Column():
                    gr.Markdown("### Variant 2")
                    buildup2_variant2 = gr.Audio(label="Variant 2")
                    select_buildup2_2_btn = gr.Button("Select Variant 2")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 3")
                    buildup2_variant3 = gr.Audio(label="Variant 3")
                    select_buildup2_3_btn = gr.Button("Select Variant 3")
                with gr.Column():
                    gr.Markdown("### Variant 4")
                    buildup2_variant4 = gr.Audio(label="Variant 4")
                    select_buildup2_4_btn = gr.Button("Select Variant 4")
        
        with gr.Accordion("Generate drop 2 Variants"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### drop 2 Parameters")
                    var2_bpm = gr.Slider(
                        label="BPM (Beats Per Minute)",
                        minimum=60,
                        maximum=180,
                        value=120,
                        step=1
                    )
                    var2_bars = gr.Slider(
                        label="Number of Bars",
                        minimum=4,
                        maximum=64,
                        value=16,
                        step=4
                    )
                    var2_p = gr.Slider(
                        label="Variation Parameter (p)",
                        minimum=0,
                        maximum=1,
                        value=0.6,
                        step=0.1
                    )
                    
                    generate_var2_btn = gr.Button("Generate drop 2 Variants", variant="primary")
                    
                with gr.Column(scale=2):
                    var2_status = gr.Textbox(label="Status", interactive=False)
                    var2_descriptions = gr.JSON(label="Variant Descriptions")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 1")
                    var2_variant1 = gr.Audio(label="Variant 1")
                    select_var2_1_btn = gr.Button("Select Variant 1")
                with gr.Column():
                    gr.Markdown("### Variant 2")
                    var2_variant2 = gr.Audio(label="Variant 2")
                    select_var2_2_btn = gr.Button("Select Variant 2")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 3")
                    var2_variant3 = gr.Audio(label="Variant 3")
                    select_var2_3_btn = gr.Button("Select Variant 3")
                with gr.Column():
                    gr.Markdown("### Variant 4")
                    var2_variant4 = gr.Audio(label="Variant 4")
                    select_var2_4_btn = gr.Button("Select Variant 4")
                    
        with gr.Accordion("Generate Outro Variants"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Outro Parameters")
                    outro_bpm = gr.Slider(
                        label="BPM (Beats Per Minute)",
                        minimum=60,
                        maximum=180,
                        value=120,
                        step=1
                    )
                    outro_bars = gr.Slider(
                        label="Number of Bars",
                        minimum=4,
                        maximum=64,
                        value=8,
                        step=4
                    )
                    outro_p = gr.Slider(
                        label="Variation Parameter (p)",
                        minimum=0,
                        maximum=1,
                        value=0.3,
                        step=0.1
                    )
                    
                    generate_outro_btn = gr.Button("Generate Outro Variants", variant="primary")
                    
                with gr.Column(scale=2):
                    outro_status = gr.Textbox(label="Status", interactive=False)
                    outro_descriptions = gr.JSON(label="Variant Descriptions")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 1")
                    outro_variant1 = gr.Audio(label="Variant 1")
                    select_outro_1_btn = gr.Button("Select Variant 1")
                with gr.Column():
                    gr.Markdown("### Variant 2")
                    outro_variant2 = gr.Audio(label="Variant 2")
                    select_outro_2_btn = gr.Button("Select Variant 2")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Variant 3")
                    outro_variant3 = gr.Audio(label="Variant 3")
                    select_outro_3_btn = gr.Button("Select Variant 3")
                with gr.Column():
                    gr.Markdown("### Variant 4")
                    outro_variant4 = gr.Audio(label="Variant 4")
                    select_outro_4_btn = gr.Button("Select Variant 4")
    
    with gr.Tab("3. Create Full Track"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Track Settings")
                crossfade_ms = gr.Slider(
                    label="Crossfade Duration (ms)",
                    minimum=0,
                    maximum=2000,
                    value=500,
                    step=100
                )
                output_track_name = gr.Textbox(
                    label="Output Filename",
                    value="full_track_output.wav",
                    placeholder="e.g., full_track_output.wav"
                )
                
                gr.Markdown("### Sections to Include")
                include_intro = gr.Checkbox(label="Include Intro", value=True)
                include_breakdown1 = gr.Checkbox(label="Include breakdown 1", value=True)
                include_drop1 = gr.Checkbox(label="Include drop 1", value=True)
                include_breakdown2 = gr.Checkbox(label="Include breakdown 2", value=True)
                include_drop2 = gr.Checkbox(label="Include drop 2", value=True)
                include_outro = gr.Checkbox(label="Include Outro", value=True)
                
                generate_track_btn = gr.Button("Generate Full Track", variant="primary", scale=2)
                
            with gr.Column():
                track_status = gr.Textbox(label="Status", interactive=False)
                track_summary = gr.JSON(label="Track Summary")
                full_track_audio = gr.Audio(label="Generated Full Track")
    
    # Event handlers
    upload_btn.click(
        fn=process_uploaded_files,
        inputs=[file_input],
        outputs=[upload_status, stem_display]
    )
    
    # buildup 1 generation and selection
    buildup1_type = gr.State("buildup1")
    generate_buildup1_btn.click(
        fn=generate_section_variants_handler,
        inputs=[
            buildup1_type,  # Fixed section type
            buildup1_bpm,
            buildup1_bars,
            buildup1_p
        ],
        outputs=[
            buildup1_status,
            buildup1_variant1,
            buildup1_variant2,
            buildup1_variant3,
            buildup1_variant4,
            buildup1_descriptions
        ]
    )
    buildup1_variant_1 = gr.State(1)
    buildup1_variant_2 = gr.State(2)
    buildup1_variant_3 = gr.State(3)
    buildup1_variant_4 = gr.State(4)
    
    select_buildup1_1_btn.click(
        fn=select_variant,
        inputs=[buildup1_type, buildup1_variant_1],
        outputs=[buildup1_status]
    )
    
    select_buildup1_2_btn.click(
        fn=select_variant,
        inputs=[buildup1_type, buildup1_variant_2],
        outputs=[buildup1_status]
    )
    
    select_buildup1_3_btn.click(
        fn=select_variant,
        inputs=[buildup1_type, buildup1_variant_3],
        outputs=[buildup1_status]
    )
    
    select_buildup1_4_btn.click(
        fn=select_variant,
        inputs=[buildup1_type, buildup1_variant_4],
        outputs=[buildup1_status]
    )
    
    # Intro generation and selection
    intro_type = gr.State("intro")
    generate_intro_btn.click(
        fn=generate_section_variants_handler,
        inputs=[
            intro_type,  # Fixed section type
            intro_bpm,
            intro_bars,
            intro_p
        ],
        outputs=[
            intro_status,
            intro_variant1,
            intro_variant2,
            intro_variant3,
            intro_variant4,
            intro_descriptions
        ]
    )
    intro_variant_1 = gr.State(1)
    intro_variant_2 = gr.State(2)
    intro_variant_3 = gr.State(3)
    intro_variant_4 = gr.State(4)
    
    select_intro_1_btn.click(
        fn=select_variant,
        inputs=[intro_type, intro_variant_1],
        outputs=[intro_status]
    )
    
    select_intro_2_btn.click(
        fn=select_variant,
        inputs=[intro_type, intro_variant_2],
        outputs=[intro_status]
    )
    
    select_intro_3_btn.click(
        fn=select_variant,
        inputs=[intro_type, intro_variant_3],
        outputs=[intro_status]
    )
    
    select_intro_4_btn.click(
        fn=select_variant,
        inputs=[intro_type, intro_variant_4],
        outputs=[intro_status]
    )
    
    # breakdown 1 generation and selection
    var1_type = gr.State("breakdown1")
    generate_var1_btn.click(
        fn=generate_section_variants_handler,
        inputs=[
            var1_type,  # Fixed section type
            var1_bpm,
            var1_bars,
            var1_p
        ],
        outputs=[
            var1_status,
            var1_variant1,
            var1_variant2,
            var1_variant3,
            var1_variant4,
            var1_descriptions
        ]
    )
    var1_variant_1 = gr.State(1)
    var1_variant_2 = gr.State(2)
    var1_variant_3 = gr.State(3)
    var1_variant_4 = gr.State(4)
    
    select_var1_1_btn.click(
        fn=select_variant,
        inputs=[var1_type, var1_variant_1],
        outputs=[var1_status]
    )
    
    select_var1_2_btn.click(
        fn=select_variant,
        inputs=[var1_type, var1_variant_2],
        outputs=[var1_status]
    )
    
    select_var1_3_btn.click(
        fn=select_variant,
        inputs=[var1_type, var1_variant_3],
        outputs=[var1_status]
    )
    
    select_var1_4_btn.click(
        fn=select_variant,
        inputs=[var1_type, var1_variant_4],
        outputs=[var1_status]
    )
    
    # drop 1 generation and selection
    var2_type = gr.State("drop1")
    generate_var2_btn.click(
        fn=generate_section_variants_handler,
        inputs=[
            var2_type,  # Fixed section type
            var2_bpm,
            var2_bars,
            var2_p
        ],
        outputs=[
            var2_status,
            var2_variant1,
            var2_variant2,
            var2_variant3,
            var2_variant4,
            var2_descriptions
        ]
    )
    var2_variant_1 = gr.State(1)
    var2_variant_2 = gr.State(2)
    var2_variant_3 = gr.State(3)
    var2_variant_4 = gr.State(4)
    
    select_var2_1_btn.click(
        fn=select_variant,
        inputs=[var2_type, var2_variant_1],
        outputs=[var2_status]
    )
    
    select_var2_2_btn.click(
        fn=select_variant,
        inputs=[var2_type, var2_variant_2],
        outputs=[var2_status]
    )
    
    select_var2_3_btn.click(
        fn=select_variant,
        inputs=[var2_type, var2_variant_3],
        outputs=[var2_status]
    )
    
    select_var2_4_btn.click(
        fn=select_variant,
        inputs=[var2_type, var2_variant_4],
        outputs=[var2_status]
    )
    
    # breakdown 2 generation and selection
    var3_type = gr.State("breakdown2")
    generate_var3_btn.click(
        fn=generate_section_variants_handler,
        inputs=[
            var3_type,  # Fixed section type
            var3_bpm,
            var3_bars,
            var3_p
        ],
        outputs=[
            var3_status,
            var3_variant1,
            var3_variant2,
            var3_variant3,
            var3_variant4,
            var3_descriptions
        ]
    )
    var3_variant_1 = gr.State(1)
    var3_variant_2 = gr.State(2)
    var3_variant_3 = gr.State(3)
    var3_variant_4 = gr.State(4)
    
    select_var3_1_btn.click(
        fn=select_variant,
        inputs=[var3_type, var3_variant_1],
        outputs=[var3_status]
    )
    
    select_var3_2_btn.click(
        fn=select_variant,
        inputs=[var3_type, var3_variant_2],
        outputs=[var3_status]
    )
    
    select_var3_3_btn.click(
        fn=select_variant,
        inputs=[var3_type, var3_variant_3],
        outputs=[var3_status]
    )
    
    select_var3_4_btn.click(
        fn=select_variant,
        inputs=[var3_type, var3_variant_4],
        outputs=[var3_status]
    )
    
    # buildup 2 generation and selection
    buildup2_type = gr.State("buildup2")
    generate_buildup2_btn.click(
        fn=generate_section_variants_handler,
        inputs=[
            buildup2_type,  # Fixed section type
            buildup2_bpm,
            buildup2_bars,
            buildup2_p
        ],
        outputs=[
            buildup2_status,
            buildup2_variant1,
            buildup2_variant2,
            buildup2_variant3,
            buildup2_variant4,
            buildup2_descriptions
        ]
    )
    buildup2_variant_1 = gr.State(1)
    buildup2_variant_2 = gr.State(2)
    buildup2_variant_3 = gr.State(3)
    buildup2_variant_4 = gr.State(4)
    
    select_buildup2_1_btn.click(
        fn=select_variant,
        inputs=[buildup2_type, buildup2_variant_1],
        outputs=[buildup2_status]
    )
    
    select_buildup2_2_btn.click(
        fn=select_variant,
        inputs=[buildup2_type, buildup2_variant_2],
        outputs=[buildup2_status]
    )
    
    select_buildup2_3_btn.click(
        fn=select_variant,
        inputs=[buildup2_type, buildup2_variant_3],
        outputs=[buildup2_status]
    )
    
    select_buildup2_4_btn.click(
        fn=select_variant,
        inputs=[buildup2_type, buildup2_variant_4],
        outputs=[buildup2_status]
    )
    
    
    # drop 2 generation and selection
    var2_type = gr.State("drop2")
    generate_var2_btn.click(
        fn=generate_section_variants_handler,
        inputs=[
            var2_type,  # Fixed section type
            var2_bpm,
            var2_bars,
            var2_p
        ],
        outputs=[
            var2_status,
            var2_variant1,
            var2_variant2,
            var2_variant3,
            var2_variant4,
            var2_descriptions
        ]
    )
    var2_variant_1 = gr.State(1)
    var2_variant_2 = gr.State(2)
    var2_variant_3 = gr.State(3)
    var2_variant_4 = gr.State(4)
    
    select_var2_1_btn.click(
        fn=select_variant,
        inputs=[var2_type, var2_variant_1],
        outputs=[var2_status]
    )
    
    select_var2_2_btn.click(
        fn=select_variant,
        inputs=[var2_type, var2_variant_2],
        outputs=[var2_status]
    )
    
    select_var2_3_btn.click(
        fn=select_variant,
        inputs=[var2_type, var2_variant_3],
        outputs=[var2_status]
    )
    
    select_var2_4_btn.click(
        fn=select_variant,
        inputs=[var2_type, var2_variant_4],
        outputs=[var2_status]
    )
    
    # Outro generation and selection
    outro_type = gr.State("outro")
    generate_outro_btn.click(
        fn=generate_section_variants_handler,
        inputs=[
            outro_type,  # Fixed section type
            outro_bpm,
            outro_bars,
            outro_p
        ],
        outputs=[
            outro_status,
            outro_variant1,
            outro_variant2,
            outro_variant3,
            outro_variant4,
            outro_descriptions
        ]
    )
    outro_variant_1 = gr.State(1)
    outro_variant_2 = gr.State(2)
    outro_variant_3 = gr.State(3)
    outro_variant_4 = gr.State(4)
    
    select_outro_1_btn.click(
        fn=select_variant,
        inputs=[outro_type, outro_variant_1],
        outputs=[outro_status]
    )
    
    select_outro_2_btn.click(
        fn=select_variant,
        inputs=[outro_type, outro_variant_2],
        outputs=[outro_status]
    )
    
    select_outro_3_btn.click(
        fn=select_variant,
        inputs=[outro_type, outro_variant_3],
        outputs=[outro_status]
    )
    
    select_outro_4_btn.click(
        fn=select_variant,
        inputs=[outro_type, outro_variant_4],
        outputs=[outro_status]
    )
    
    # Generate full track
    generate_track_btn.click(
        fn=generate_full_track,
        inputs=[
            crossfade_ms,
            output_track_name,
            include_intro,
            include_breakdown1,
            include_drop1,
            include_breakdown2,
            include_drop2,
            include_outro
        ],
        outputs=[
            track_status,
            full_track_audio,
            track_summary
        ]
    )

if __name__ == "__main__":
    demo.launch()