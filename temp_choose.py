import gradio as gr
import plotly.graph_objects as go
import numpy as np
import json

# Three base arrangements
arrangements = {
    "High Energy Flow": [
        (1, 16, "Intro", 16, "Linear"),           
        (17, 48, "Verse 1", 32, "Flat"),          
        (49, 64, "Build-Up", 16, "Linear"),       
        (65, 100, "Drop 1", 64, "Flat"),          
        (129, 40, "Breakdown", 16, "-ve Linear"),
        (145, 60, "Bridge", 32, "Flat"),         
        (177, 64, "Build-Up", 16, "Linear"),     
        (193, 100, "Drop 2", 64, "Flat"),         
        (257, 40, "Outro/Fade", 16, "-ve Linear")
    ],
    "Festival Vibes": [
        (1, 20, "Intro", 8, "Linear"),             
        (9, 40, "Verse 1", 32, "Flat"),           
        (41, 60, "Pre-Chorus", 16, "Linear"),     
        (57, 100, "Drop 1", 64, "Flat"),          
        (121, 40, "Breakdown", 16, "-ve Linear"),
        (137, 60, "Bridge", 32, "Flat"),         
        (169, 64, "Build-Up", 16, "Linear"),     
        (185, 100, "Drop 2", 64, "Flat"),         
        (249, 40, "Outro/Fade", 16, "-ve Linear")
    ],
    "Underground Pulse": [
        (1, 20, "Intro", 16, "Linear"),           
        (17, 40, "Verse 1", 32, "Flat"),          
        (49, 40, "Breakdown", 16, "-ve Linear"),  
        (65, 60, "Build-Up", 16, "Linear"),       
        (81, 100, "Drop 1", 64, "Flat"),          
        (145, 40, "Bridge", 16, "-ve Linear"),   
        (161, 60, "Pre-Chorus", 32, "Linear"),   
        (193, 100, "Drop 2", 64, "Flat"),         
        (257, 40, "Outro", 16, "-ve Linear")     
    ]
}

arrangement = arrangements["High Energy Flow"].copy()

def shift_arrangement(start_index):
    for i in range(start_index + 1, len(arrangement)):
        prev_start, _, _, prev_length, _ = arrangement[i - 1]
        arrangement[i] = (prev_start + prev_length, *arrangement[i][1:])

def editable_diagram(section_data):
    fig = go.Figure()
    total_bars = 0
    for bar, tempo, name, length, curve in section_data:
        x = np.arange(bar, bar + length + 1)
        if curve == "Linear":
            y = np.linspace(tempo * 0.6, tempo, len(x))
        elif curve == "-ve Linear":
            y = np.linspace(tempo, tempo * 0.6, len(x))
        else:
            y = np.full(len(x), tempo)
        fig.add_trace(go.Scatter(x=x, y=y, fill='tozeroy', name=name, mode='lines', line_shape='hv'))
        total_bars = max(total_bars, bar + length)

    fig.update_layout(title="EDM Arrangement Energy Curve",
                      xaxis_title="Bar",
                      yaxis_title="Volume (Energy)",
                      xaxis=dict(range=[0, total_bars + 4]),
                      yaxis=dict(range=[0, 100]),
                      height=400)
    return fig

def update_section(index, bar, tempo, length, curve):
    global arrangement
    current = arrangement[index]
    arrangement[index] = (int(bar), int(tempo), current[2], int(length), curve)
    shift_arrangement(index)
    return editable_diagram(arrangement)

def insert_section(index, name="New Section", bar=0, tempo=50, length=8, curve="Flat"):
    global arrangement
    arrangement.insert(index, (bar, tempo, name, length, curve))
    shift_arrangement(index)
    return editable_diagram(arrangement)

def load_variation(variation_name):
    global arrangement
    arrangement = arrangements[variation_name].copy()
    return editable_diagram(arrangement)

def finalise():
    with open("final_arrangement.json", "w") as f:
        json.dump(arrangement, f, indent=2)
    return json.dumps(arrangement, indent=2)

with gr.Blocks() as iface:
    gr.Markdown("# 🌚 Interactive EDM Arrangement Tool")

    with gr.Row():
        variation = gr.Radio(choices=list(arrangements.keys()), value="High Energy Flow", label="Choose Arrangement Variation")

    out_plot = gr.Plot(label="Arrangement Diagram")
    variation.change(fn=load_variation, inputs=variation, outputs=out_plot)
    out_plot.value = editable_diagram(arrangement)

    with gr.Accordion("🎻 Edit Section Parameters", open=False):
        for i, (bar, tempo, name, length, curve) in enumerate(arrangement):
            with gr.Row():
                gr.Markdown(f"**{name}**")
                bar_slider = gr.Slider(minimum=0, maximum=300, value=bar, label="Start Bar")
                tempo_slider = gr.Slider(minimum=20, maximum=100, value=tempo, label="Volume")
                length_slider = gr.Slider(minimum=1, maximum=64, value=length, label="Length")
                curve_selector = gr.Radio(choices=["Flat", "Linear", "-ve Linear"], value=curve, label="Curve Type")
                update_btn = gr.Button("Update")
                update_btn.click(fn=update_section,
                                 inputs=[gr.Number(value=i, visible=False), bar_slider, tempo_slider, length_slider, curve_selector],
                                 outputs=[out_plot])

    with gr.Accordion("➕ Insert New Section", open=False):
        new_index = gr.Number(value=0, label="Insert At Index")
        new_name = gr.Textbox(label="Section Name", value="New Section")
        new_bar = gr.Slider(minimum=0, maximum=300, value=0, label="Start Bar")
        new_tempo = gr.Slider(minimum=20, maximum=100, value=50, label="Volume")
        new_length = gr.Slider(minimum=1, maximum=64, value=8, label="Length")
        new_curve = gr.Radio(choices=["Flat", "Linear", "-ve Linear"], value="Flat", label="Curve Type")
        insert_btn = gr.Button("Insert Section")
        insert_btn.click(fn=insert_section, inputs=[new_index, new_name, new_bar, new_tempo, new_length, new_curve], outputs=[out_plot])

    gr.Markdown("## ✅ Finalise Your Arrangement")
    final_btn = gr.Button("Finalise and Export JSON")
    final_output = gr.Textbox(label="Final Arrangement JSON", lines=15)
    final_btn.click(fn=finalise, outputs=final_output)

iface.launch()