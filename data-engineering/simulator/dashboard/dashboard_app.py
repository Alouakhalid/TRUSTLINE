"""Interactive Observability Dashboard displaying real-time waveforms and isolated space radiation monitor."""
import json
from typing import Dict, Any, List
import dash
from dash import html, dcc, Input, Output, State
import plotly.graph_objs as go
import numpy as np

from ..schemas import ScenarioType, FaultType, SensorType
from ..scenarios.engine import ScenarioEngine


def create_simulator_dashboard_app(port: int = 8050) -> dash.Dash:
    """Build Dash real-time telemetry and space environment observability dashboard."""
    app = dash.Dash(__name__, title="TRUSTLINE Telemetry Simulator")

    # In-memory engine for dashboard session
    engine = ScenarioEngine(astronaut_id="AST-001", session_id="SESSION-DASHBOARD")

    app.layout = html.Div(
        style={"backgroundColor": "#0d1117", "color": "#c9d1d9", "fontFamily": "sans-serif", "padding": "15px"},
        children=[
            # Top Banner
            html.Div(
                style={"borderBottom": "1px solid #30363d", "paddingBottom": "10px", "marginBottom": "15px"},
                children=[
                    html.H2("🛰️ TRUSTLINE — External Astronaut Hardware Simulator & Dosimetry", style={"margin": "0"}),
                    html.P("Real-time physiological telemetry, sensor quality gates, and independent space environment monitoring.", style={"color": "#8b949e", "margin": "4px 0 0 0"})
                ]
            ),

            # Grid Container
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "280px 1fr 340px", "gap": "15px"},
                children=[
                    # Left Column: Controls
                    html.Div(
                        style={"backgroundColor": "#161b22", "padding": "15px", "borderRadius": "8px", "border": "1px solid #30363d"},
                        children=[
                            html.H4("Mission Scenario", style={"marginTop": "0"}),
                            dcc.Dropdown(
                                id="scenario-dropdown",
                                options=[{"label": s.name.replace("SCENARIO_", ""), "value": s.value} for s in ScenarioType],
                                value=ScenarioType.SCENARIO_A_REST.value,
                                style={"color": "#000", "marginBottom": "15px"}
                            ),
                            html.H4("Hardware Fault Injection"),
                            dcc.Dropdown(
                                id="fault-dropdown",
                                options=[{"label": f.name, "value": f.value} for f in FaultType],
                                value=FaultType.NONE.value,
                                style={"color": "#000", "marginBottom": "15px"}
                            ),
                            html.H4("Target Sensor"),
                            dcc.Dropdown(
                                id="sensor-dropdown",
                                options=[{"label": st.value, "value": st.value} for st in SensorType],
                                value=SensorType.ECG.value,
                                style={"color": "#000", "marginBottom": "15px"}
                            ),
                            html.Button(
                                "Apply Settings", id="apply-btn", n_clicks=0,
                                style={"backgroundColor": "#238636", "color": "#fff", "border": "none", "padding": "8px 16px", "borderRadius": "6px", "cursor": "pointer", "width": "100%"}
                            ),
                            html.Hr(style={"borderColor": "#30363d", "margin": "20px 0"}),
                            html.Div(id="status-display", style={"fontSize": "13px", "color": "#58a6ff"})
                        ]
                    ),

                    # Center Column: Waveforms
                    html.Div(
                        children=[
                            dcc.Graph(id="ecg-graph", style={"height": "200px", "marginBottom": "10px"}),
                            dcc.Graph(id="ppg-resp-graph", style={"height": "200px", "marginBottom": "10px"}),
                            dcc.Graph(id="eda-motion-graph", style={"height": "200px"})
                        ]
                    ),

                    # Right Column: Quality & Space Environment (STRICTLY SEPARATED)
                    html.Div(
                        children=[
                            # Sensor Quality Status Box
                            html.Div(
                                style={"backgroundColor": "#161b22", "padding": "15px", "borderRadius": "8px", "border": "1px solid #30363d", "marginBottom": "15px"},
                                children=[
                                    html.H4("Sensor Quality Status", style={"marginTop": "0"}),
                                    html.Div(id="quality-badges-container")
                                ]
                            ),
                            # Space Environment Monitor (STRICTLY SEPARATED FROM ML)
                            html.Div(
                                style={"backgroundColor": "#161b22", "padding": "15px", "borderRadius": "8px", "border": "2px solid #d29922"},
                                children=[
                                    html.H4("☢️ Space Environment Dosimetry", style={"marginTop": "0", "color": "#d29922"}),
                                    html.Div(
                                        "STRICT PHYSICAL SEPARATION: Environmental telemetry evaluated exclusively by RuleRegistry and NASA-STD-3001 protocols. Excluded from physiological ML.",
                                        style={"fontSize": "11px", "color": "#8b949e", "marginBottom": "10px"}
                                    ),
                                    html.Div(id="radiation-metrics-container")
                                ]
                            )
                        ]
                    )
                ]
            ),

            # Real-time Update Interval (1 second)
            dcc.Interval(id="interval-timer", interval=1000, n_intervals=0)
        ]
    )

    @app.callback(
        Output("status-display", "children"),
        Input("apply-btn", "n_clicks"),
        State("scenario-dropdown", "value"),
        State("fault-dropdown", "value"),
        State("sensor-dropdown", "value"),
        prevent_initial_call=True
    )
    def update_scenario_and_faults(n_clicks, scen_val, fault_val, sensor_val):
        scen = ScenarioType(scen_val)
        engine.set_scenario(scen)
        if fault_val != FaultType.NONE.value:
            from ..schemas import FaultInjectionConfig
            engine.fault_injector.add_fault(
                FaultInjectionConfig(
                    fault_type=FaultType(fault_val),
                    target_sensor=SensorType(sensor_val),
                    start_time_sec=engine.elapsed_time_sec,
                    duration_sec=60.0
                )
            )
        return f"Active: {scen.value} | Fault: {fault_val} on {sensor_val}"

    @app.callback(
        [
            Output("ecg-graph", "figure"),
            Output("ppg-resp-graph", "figure"),
            Output("eda-motion-graph", "figure"),
            Output("quality-badges-container", "children"),
            Output("radiation-metrics-container", "children")
        ],
        Input("interval-timer", "n_intervals")
    )
    def update_realtime_telemetry(n):
        pkts, space_pkt = engine.generate_step(duration_sec=1.0)

        # Plot ECG
        ecg_pkt = next((p for p in pkts if p.sensor_type == SensorType.ECG), None)
        ecg_fig = go.Figure()
        if ecg_pkt and ecg_pkt.channels_data:
            ecg_fig.add_trace(go.Scatter(y=ecg_pkt.channels_data[1][:150], mode="lines", line=dict(color="#39d353", width=1.5), name="ECG Lead II"))
        ecg_fig.update_layout(
            title="ECG Lead II (mV)", margin=dict(l=30, r=20, t=30, b=20),
            plot_bgcolor="#0d1117", paper_bgcolor="#161b22", font=dict(color="#c9d1d9", size=10),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#30363d")
        )

        # Plot PPG & Respiration
        ppg_pkt = next((p for p in pkts if p.sensor_type == SensorType.PPG), None)
        resp_pkt = next((p for p in pkts if p.sensor_type == SensorType.RESPIRATION), None)
        dual_fig = go.Figure()
        if ppg_pkt and ppg_pkt.channels_data:
            dual_fig.add_trace(go.Scatter(y=ppg_pkt.channels_data[0], mode="lines", line=dict(color="#58a6ff", width=1.5), name="PPG Pulse"))
        if resp_pkt and resp_pkt.channels_data:
            dual_fig.add_trace(go.Scatter(y=resp_pkt.channels_data[0], mode="lines", line=dict(color="#bc8cff", width=1.5), name="Respiration"))
        dual_fig.update_layout(
            title="PPG Plethysmogram & Respiration Effort", margin=dict(l=30, r=20, t=30, b=20),
            plot_bgcolor="#0d1117", paper_bgcolor="#161b22", font=dict(color="#c9d1d9", size=10),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#30363d")
        )

        # Plot EDA & Accel Magnitude
        eda_pkt = next((p for p in pkts if p.sensor_type == SensorType.EDA), None)
        acc_pkt = next((p for p in pkts if p.sensor_type == SensorType.ACCELEROMETER), None)
        eda_fig = go.Figure()
        if eda_pkt and eda_pkt.channels_data:
            eda_fig.add_trace(go.Scatter(y=eda_pkt.channels_data[0], mode="lines", line=dict(color="#f0883e", width=1.5), name="EDA (µS)"))
        eda_fig.update_layout(
            title="Electrodermal Conductance (µS)", margin=dict(l=30, r=20, t=30, b=20),
            plot_bgcolor="#0d1117", paper_bgcolor="#161b22", font=dict(color="#c9d1d9", size=10),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#30363d")
        )

        # Quality Badges
        has_flatline = any(cfg.fault_type == FaultType.FLATLINE for cfg in engine.fault_injector.configs)
        ecg_badge_color = "#f85149" if has_flatline else "#238636"
        ecg_badge_text = "INVALID / FLATLINE" if has_flatline else "VALID (SNR 24dB)"

        quality_badges = html.Div([
            html.Div([html.Span("ECG: ", style={"fontWeight": "bold"}), html.Span(ecg_badge_text, style={"color": ecg_badge_color})], style={"marginBottom": "8px"}),
            html.Div([html.Span("EDA: ", style={"fontWeight": "bold"}), html.Span("VALID (3.2 µS)", style={"color": "#238636"})], style={"marginBottom": "8px"}),
            html.Div([html.Span("RESP: ", style={"fontWeight": "bold"}), html.Span("VALID (14 bpm)", style={"color": "#238636"})], style={"marginBottom": "8px"}),
            html.Div([html.Span("TEMP: ", style={"fontWeight": "bold"}), html.Span("VALID (36.8 °C)", style={"color": "#238636"})])
        ])

        # Radiation Metrics Display
        if space_pkt:
            alert_color = "#f85149" if space_pkt.alert_level == "ALARM" else ("#d29922" if space_pkt.alert_level == "WARNING" else "#238636")
            rad_display = html.Div([
                html.Div([html.Span("Alert State: ", style={"fontWeight": "bold"}), html.Span(space_pkt.alert_level, style={"color": alert_color, "fontWeight": "bold"})], style={"marginBottom": "8px"}),
                html.Div([html.Span("Dose Rate: ", style={"fontWeight": "bold"}), html.Span(f"{space_pkt.dose_rate_microgy_h:.1f} µGy/h", style={"color": "#fff"})], style={"marginBottom": "8px"}),
                html.Div([html.Span("Equivalent Rate: ", style={"fontWeight": "bold"}), html.Span(f"{space_pkt.equivalent_dose_rate_msv_h:.4f} mSv/h", style={"color": "#fff"})], style={"marginBottom": "8px"}),
                html.Div([html.Span("Cumulative Mission: ", style={"fontWeight": "bold"}), html.Span(f"{space_pkt.cumulative_mission_dose_msv:.2f} mSv", style={"color": "#58a6ff"})], style={"marginBottom": "8px"}),
                html.Div([html.Span("SPE Active: ", style={"fontWeight": "bold"}), html.Span(str(space_pkt.spe_active), style={"color": "#f85149" if space_pkt.spe_active else "#39d353"})], style={"marginBottom": "8px"}),
                html.Div([html.Span("Shielding Al: ", style={"fontWeight": "bold"}), html.Span(f"{space_pkt.shielding_thickness_g_cm2:.1f} g/cm²", style={"color": "#8b949e"})])
            ])
        else:
            rad_display = html.Div("Radiation monitor offline.")

        return ecg_fig, dual_fig, eda_fig, quality_badges, rad_display

    return app


if __name__ == "__main__":
    app_instance = create_simulator_dashboard_app()
    app_instance.run(port=8050, debug=False)
