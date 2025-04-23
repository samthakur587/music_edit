import os
import gradio as gr
import json
import logging
import shutil
import tempfile
from pathlib import Path
import numpy as np
from utils import (
    rename_files_remove_spaces,
    load_audio_files,
    get_stems,
    generate_section_variants,
    export_section_variants,
    edm_arrangement_tab,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Global variable to store the temporary directory
TEMP_DIR = "test"
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
        TEMP_DIR = "test" #tempfile.mkdtemp()
        try:
            # Copy uploaded files to temp directory
            progress(0.2, desc="Copying uploaded files...")
            for file in files:
                if file.name.lower().endswith(".wav"):
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
    section_type, bpm_value, bars_value, p_value, progress=gr.Progress()
):
    """Handler function for generating section variants"""
    global TEMP_DIR, ALL_VARIANTS, UPLOADED_STEMS

    if not TEMP_DIR or not os.path.exists(TEMP_DIR):
        return (
            "Error: No stems loaded. Please upload stems first.",
            None,
            None,
            None,
            None,
        )

    try:
        progress(0.1, desc=f"Generating {section_type} variants...")

        # Generate variants
        variants = generate_section_variants(
            TEMP_DIR,
            UPLOADED_STEMS,
            section_type,
            bpm=int(bpm_value),
            bars=int(bars_value),
            p=float(p_value),
        )
        
        logger.info(f"S1: VARIANTS of section {section_type} : {variants}")
        
        progress(0.4, desc="Variants generated")

        # Store variants for later use
        ALL_VARIANTS[section_type] = variants

        progress(0.6, desc="Exporting audio files...")

        # Export variants to audio files
        variant_output_dir = os.path.join(TEMP_DIR, section_type + "_variants")
        audio_paths = export_section_variants(
            variants, variant_output_dir, section_type
        )
        
        logger.info(f"S2: AUDIO_PATHS of section {section_type} : {audio_paths}")

        # Create audio elements for each variant
        variant1_audio = audio_paths.get("variant1")
        variant2_audio = audio_paths.get("variant2")
        variant3_audio = audio_paths.get("variant3")
        variant4_audio = audio_paths.get("variant4")

        # Descriptions
        descriptions = {key: data["description"] for key, data in variants.items()}
        descriptions_json = json.dumps(descriptions, indent=2)
        
        logger.info(f"S3: DESCRIPTIONS of section {section_type} : {descriptions_json}")

        progress(1.0, desc="Complete!")

        return (
            f"Generated {len(variants)} variants for {section_type}",
            variant1_audio,
            variant2_audio,
            variant3_audio,
            variant4_audio,
            descriptions_json,
        )

    except Exception as e:
        return f"Error generating variants: {str(e)}", None, None, None, None, None


def select_variant(section_type, variant_num, append):
    """Select a variant for a specific section, with an option to append"""
    global ALL_VARIANTS, SELECTED_VARIANTS

    if section_type not in ALL_VARIANTS:
        return f"No variants generated for {section_type} yet"

    variant_key = f"variant{variant_num}"
    if variant_key not in ALL_VARIANTS[section_type]:
        return f"Variant {variant_num} not found for {section_type}"

    # If appending, add to the list of selected variants
    if append:
        if section_type not in SELECTED_VARIANTS:
            SELECTED_VARIANTS[section_type] = []
        SELECTED_VARIANTS[section_type].append(
            ALL_VARIANTS[section_type][variant_key]["config"]
        )
    else:
        # Otherwise, replace the selection
        SELECTED_VARIANTS[section_type] = [
            ALL_VARIANTS[section_type][variant_key]["config"]
        ]

    return f"Selected variant {variant_num} for {section_type} (Append: {append})"


def generate_full_track(
    crossfade_ms,
    output_track_name,
    include_intro,
    include_buildup,
    include_breakdown,
    include_drop,
    include_outro,
    progress=gr.Progress(),
):
    """Generate the full track from selected variants"""
    global TEMP_DIR, SELECTED_VARIANTS, UPLOADED_STEMS

    if not TEMP_DIR or not os.path.exists(TEMP_DIR):
        return "Error: No stems loaded", None, None

    try:
        progress(0.1, desc="Preparing to generate full track...")

        # Check which sections to include based on user selections and available variants
        sections_to_include = {}
        logger.info(f"SELECTED_VARIANTS: {SELECTED_VARIANTS}")

        if include_intro and "intro" in SELECTED_VARIANTS:
            sections_to_include["intro"] = SELECTED_VARIANTS["intro"]

        if include_buildup and "buildup" in SELECTED_VARIANTS:
            sections_to_include["buildup"] = SELECTED_VARIANTS["buildup"]

        # We always include the full loop if it exists
        if "full_loop" in SELECTED_VARIANTS:
            sections_to_include["full_loop"] = SELECTED_VARIANTS["full_loop"]

        if include_breakdown and "breakdown" in SELECTED_VARIANTS:
            sections_to_include["breakdown"] = SELECTED_VARIANTS["breakdown"]

        if include_drop and "drop" in SELECTED_VARIANTS:
            sections_to_include["drop"] = SELECTED_VARIANTS["drop"]

        if include_outro and "outro" in SELECTED_VARIANTS:
            sections_to_include["outro"] = SELECTED_VARIANTS["outro"]

        if not sections_to_include:
            return "Error: No sections selected or available", None, None

        progress(0.3, desc="Creating track structure...")

        # Create the final track
        final_track = None

        # Define the order of sections
        section_order = ["intro", "buildup", "full_loop", "breakdown", "drop", "outro"]

        # Process each section in order
        for section_name in section_order:
            if section_name not in sections_to_include:
                continue

            progress(
                0.4 + 0.1 * section_order.index(section_name) / len(section_order),
                desc=f"Processing {section_name}...",
            )

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
            "Crossfade": f"{crossfade_ms} ms",
        }

        progress(1.0, desc="Complete!")

        return (
            "Track generated successfully!",
            full_track_path,
            json.dumps(track_summary, indent=2),
        )

    except Exception as e:
        return f"Error generating track: {str(e)}", None, None


def generate_full_loop_variants(bpm_value, bars_value, p_value, progress=gr.Progress()):
    """Generate variants for the full loop section"""
    return generate_section_variants_handler(
        "full_loop", bpm_value, bars_value, p_value, progress
    )


def create_section_ui(section_name, bpm_default, bars_default, p_default):
    """Helper function to create UI elements for a section."""
    with gr.Accordion(f"Generate {section_name.capitalize()} Variants", open=False):
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown(f"### {section_name.capitalize()} Parameters")
                bpm_slider = gr.Slider(
                    label="BPM (Beats Per Minute)",
                    minimum=60,
                    maximum=180,
                    value=bpm_default,
                    step=1,
                )
                bars_slider = gr.Slider(
                    label="Number of Bars", minimum=4, maximum=64, value=bars_default, step=4
                )
                p_slider = gr.Slider(
                    label="Variation Parameter (p)",
                    minimum=0,
                    maximum=1,
                    value=p_default,
                    step=0.1,
                )

                generate_btn = gr.Button(
                    f"Generate {section_name.capitalize()} Variants", variant="primary"
                )

            with gr.Column(scale=2):
                status = gr.Textbox(label="Status", interactive=False)
                descriptions = gr.JSON(label="Variant Descriptions")

        # Create empty lists to store the audio and checkbox components
        variant_audio_list = []
        select_btn_list = []
        
        with gr.Row():
            for i in range(1, 5):
                with gr.Column():
                    gr.Markdown(f"### Variant {i}")
                    # Create and immediately append each component to its respective list
                    variant_audio = gr.Audio(label=f"Variant {i}", interactive=False)
                    variant_audio_list.append(variant_audio)
                    
                    select_btn = gr.Checkbox(label=f"Select Variant {i}")
                    select_btn_list.append(select_btn)

    return {
        "bpm_slider": bpm_slider,
        "bars_slider": bars_slider,
        "p_slider": p_slider,
        "generate_btn": generate_btn,
        "status": status,
        "descriptions": descriptions,
        "variant_audio": variant_audio_list,  # Return the complete list of audio components
        "select_btn": select_btn_list,  # Return the complete list of checkbox components
    }

def setup_section_event_handlers(section_name, section_ui):
    """Setup event handlers for a given section."""
    section_type = gr.State(section_name)

    # Generate button click event
    section_ui["generate_btn"].click(
        fn=generate_section_variants_handler,
        inputs=[
            section_type,
            section_ui["bpm_slider"],
            section_ui["bars_slider"],
            section_ui["p_slider"],
        ],
        outputs=[
            section_ui["status"],
            *section_ui["variant_audio"],
            section_ui["descriptions"],
        ],
    )

    # Selection buttons change events
    for i, select_btn in enumerate(section_ui["select_btn"], start=1):
        variant_num = gr.State(i)
        select_btn.change(
            fn=select_variant,
            inputs=[section_type, variant_num, gr.State(False)],
            outputs=[section_ui["status"]],
        )


# Load section configuration from a JSON file or string
section_config_json = """
{
    "intro": {"bpm": 120, "bars": 8, "p": 0.3},
    "buildup": {"bpm": 120, "bars": 16, "p": 0.4},
    "breakdown": {"bpm": 120, "bars": 16, "p": 0.6},
    "drop": {"bpm": 120, "bars": 16, "p": 0.7},
    "outro": {"bpm": 120, "bars": 8, "p": 0.3}
}
"""

sections = json.loads(section_config_json)

# Create Gradio interface
with gr.Blocks(title="Interactive Music Track Generator") as demo:
    gr.Markdown("# Interactive Music Track Generator")
    gr.Markdown(
        "Upload your WAV stems, generate variants for each section, and create a full track"
    )

    # Global variables for UI state
    stem_list = gr.State([])

    with gr.Tab("1. Upload Stems"):
        with gr.Row():
            with gr.Column():
                # File upload section
                gr.Markdown("### Upload Files")
                gr.Markdown("Drag and drop your WAV stem files here")
                file_input = gr.File(
                    label="WAV Stems", file_count="multiple", file_types=[".wav"]
                )

                upload_btn = gr.Button("Upload and Process Files", variant="primary")

            with gr.Column():
                upload_status = gr.Textbox(label="Upload Status", interactive=False)
                stem_display = gr.JSON(label="Available Stems")

    with gr.Tab("1.1. ⏳ Finalise Sections Arrangement (In Progress)"):
        gr.Markdown("### 🎶 Finalise Sections Arrangement")
        gr.Markdown(
            "🎛️ Use the diagram below to adjust the arrangement of your sections. Click on a section to edit its properties."
        )
        # Editable diagram with progress indicator
        with gr.Row():
            gr.Markdown("⏳ In Progress: Adjusting sections...")
        edm_arrangement_tab()

    with gr.Tab("2. Generate Section Variants"):
        # Example of creating UI for sections dynamically
        section_uis = {}
        for section_name, params in sections.items():
            section_uis[section_name] = create_section_ui(
                section_name, params["bpm"], params["bars"], params["p"]
            )
            setup_section_event_handlers(section_name, section_uis[section_name])

    with gr.Tab("3. Create Full Track"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Track Settings")
                crossfade_ms = gr.Slider(
                    label="Crossfade Duration (ms)",
                    minimum=0,
                    maximum=2000,
                    value=500,
                    step=100,
                )
                output_track_name = gr.Textbox(
                    label="Output Filename",
                    value="full_track_output.wav",
                    placeholder="e.g., full_track_output.wav",
                )

                gr.Markdown("### Sections to Include")
                include_intro = gr.Checkbox(label="Include Intro", value=True)
                include_buildup = gr.Checkbox(label="Include buildup", value=True)
                include_breakdown = gr.Checkbox(label="Include breakdown", value=True)
                include_drop = gr.Checkbox(label="Include drop", value=True)
                include_outro = gr.Checkbox(label="Include Outro", value=True)

                generate_track_btn = gr.Button(
                    "Generate Full Track", variant="primary", scale=2
                )

            with gr.Column():
                track_status = gr.Textbox(label="Status", interactive=False)
                track_summary = gr.JSON(label="Track Summary")
                full_track_audio = gr.Audio(label="Generated Full Track")

    # Event handlers
    upload_btn.click(
        fn=process_uploaded_files,
        inputs=[file_input],
        outputs=[upload_status, stem_display],
    )

    # Generate full track
    generate_track_btn.click(
        fn=generate_full_track,
        inputs=[
            crossfade_ms,
            output_track_name,
            include_intro,
            include_breakdown,
            include_buildup,
            include_drop,
            include_outro,
        ],
        outputs=[track_status, full_track_audio, track_summary],
    )

if __name__ == "__main__":
    demo.launch()
