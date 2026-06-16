from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from drive_thru_model import SimulationConfig, SimulationResult, run_simulation


STAGE_POSITIONS = {
    "queue": (100, 300),
    "waiting_order": (225, 300),
    "order": (350, 245),
    "waiting_payment": (475, 300),
    "payment": (600, 245),
    "waiting_pickup": (710, 300),
    "pickup": (820, 245),
    "departed": (960, 300),
    "rejected": (960, 405),
}

CAR_COLORS = {
    "queue": "#7c3aed",
    "waiting_order": "#2563eb",
    "order": "#16a34a",
    "waiting_payment": "#0891b2",
    "payment": "#f59e0b",
    "waiting_pickup": "#db2777",
    "pickup": "#dc2626",
    "departed": "#475569",
    "rejected": "#991b1b",
}


class DriveThruApp(tk.Tk):
    # System branding configuration
    SYSTEM_NAME = "DriveQueue"
    SYSTEM_VERSION = "v1.0"
    
    def __init__(self):
        super().__init__()
        self.title(f"{self.SYSTEM_NAME} - {self.SYSTEM_VERSION}")
        self.geometry("1180x760")
        self.minsize(1080, 700)

        self.result: SimulationResult | None = None
        self.event_index = 0
        self.playing = False
        self.after_id: str | None = None
        self.inputs: dict[str, tk.StringVar] = {}

        self._build_layout()
        self._run_simulation()

    def _build_layout(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=1)

        # Branding header
        header = ttk.Frame(self, padding=10)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(1, weight=1)
        
        brand_title = ttk.Label(header, text=self.SYSTEM_NAME, font=("Segoe UI", 16, "bold"), foreground="#1e40af")
        brand_title.grid(row=0, column=0, sticky="w", padx=4)
        
        brand_version = ttk.Label(header, text=self.SYSTEM_VERSION, font=("Segoe UI", 10), foreground="#6b7280")
        brand_version.grid(row=0, column=1, sticky="e", padx=4)
        
        # Separator
        ttk.Separator(self, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew")

        controls = ttk.Frame(self, padding=14)
        controls.grid(row=2, column=0, sticky="ns")

        title = ttk.Label(controls, text="Service System Optimization", font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        fields = [
            ("Duration (min)", "duration_minutes", "1440"),
            ("Arrivals / hour", "arrival_rate_per_hour", "12"),
            ("Peak multiplier", "peak_multiplier", "2.0"),
            ("Peak start (min)", "peak_start_minute", "660"),
            ("Peak end (min)", "peak_end_minute", "840"),
            ("Order stations", "order_stations", "1"),
            ("Payment windows", "payment_windows", "1"),
            ("Pickup windows", "pickup_windows", "1"),
            ("Lane capacity", "lane_capacity", "10"),
            ("Random seed", "seed", "42"),
        ]
        for row, (label, key, default) in enumerate(fields, start=1):
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", pady=4)
            value = tk.StringVar(value=default)
            self.inputs[key] = value
            ttk.Entry(controls, textvariable=value, width=12).grid(row=row, column=1, sticky="ew", pady=4)

        ttk.Button(controls, text="Run Scenario", command=self._run_simulation).grid(
            row=12, column=0, columnspan=2, sticky="ew", pady=(12, 4)
        )
        self.play_button = ttk.Button(controls, text="Pause", command=self._toggle_playback)
        self.play_button.grid(row=13, column=0, columnspan=2, sticky="ew", pady=4)

        ttk.Label(controls, text="Animation speed").grid(row=14, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.speed = tk.DoubleVar(value=1.0)
        ttk.Scale(controls, from_=0.2, to=3.0, variable=self.speed, orient="horizontal").grid(
            row=15, column=0, columnspan=2, sticky="ew"
        )

        self.summary_text = tk.StringVar(value="")
        ttk.Label(controls, textvariable=self.summary_text, justify="left", wraplength=260).grid(
            row=16, column=0, columnspan=2, sticky="nw", pady=(16, 0)
        )
        controls.rowconfigure(16, weight=1)

        main = ttk.Frame(self, padding=(0, 14, 14, 14))
        main.grid(row=2, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)
        main.rowconfigure(1, weight=0)

        self.canvas = tk.Canvas(main, bg="#f8fafc", highlightthickness=1, highlightbackground="#cbd5e1")
        self.canvas.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Bottom section: Event log and Analysis side by side
        bottom_frame = ttk.Frame(main)
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(1, weight=1)
        bottom_frame.rowconfigure(0, weight=1)

        # Event log on the left
        log_frame = ttk.LabelFrame(bottom_frame, text="Event Log", padding=4)
        log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.event_log = tk.Text(log_frame, height=6, wrap="word", state="disabled")
        self.event_log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.event_log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.event_log.configure(yscrollcommand=scrollbar.set)

        # Analysis box on the right
        analysis_frame = ttk.LabelFrame(bottom_frame, text="Generated Analysis", padding=4)
        analysis_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        analysis_frame.columnconfigure(0, weight=1)
        analysis_frame.rowconfigure(0, weight=1)
        
        self.analysis_box = tk.Text(analysis_frame, height=6, wrap="word", state="disabled")
        self.analysis_box.grid(row=0, column=0, sticky="nsew")
        analysis_scrollbar = ttk.Scrollbar(analysis_frame, orient="vertical", command=self.analysis_box.yview)
        analysis_scrollbar.grid(row=0, column=1, sticky="ns")
        self.analysis_box.configure(yscrollcommand=analysis_scrollbar.set)

    def _config_from_inputs(self) -> SimulationConfig:
        try:
            return SimulationConfig(
                duration_minutes=int(self.inputs["duration_minutes"].get()),
                arrival_rate_per_hour=float(self.inputs["arrival_rate_per_hour"].get()),
                peak_multiplier=float(self.inputs["peak_multiplier"].get()),
                peak_start_minute=int(self.inputs["peak_start_minute"].get()),
                peak_end_minute=int(self.inputs["peak_end_minute"].get()),
                order_stations=max(1, int(self.inputs["order_stations"].get())),
                payment_windows=max(1, int(self.inputs["payment_windows"].get())),
                pickup_windows=max(1, int(self.inputs["pickup_windows"].get())),
                lane_capacity=max(1, int(self.inputs["lane_capacity"].get())),
                seed=int(self.inputs["seed"].get()),
            )
        except ValueError as exc:
            raise ValueError("Please enter valid numeric values for all scenario settings.") from exc

    def _run_simulation(self):
        try:
            config = self._config_from_inputs()
            if config.peak_end_minute <= config.peak_start_minute:
                messagebox.showerror("Scenario error", "Peak end must be greater than peak start.")
                return
        except ValueError as exc:
            messagebox.showerror("Scenario error", str(exc))
            return

        self._cancel_timer()
        self.result = run_simulation(config)
        self.event_index = 0
        self.playing = True
        self.play_button.configure(text="Pause")
        self._write_log("", clear=True)
        self._update_summary()
        self._update_analysis()
        self._draw_static_scene()
        self._advance_event()

    def _toggle_playback(self):
        self.playing = not self.playing
        self.play_button.configure(text="Pause" if self.playing else "Play")
        if self.playing:
            self._advance_event()
        else:
            self._cancel_timer()

    def _advance_event(self):
        if not self.result or not self.playing:
            return
        if self.event_index >= len(self.result.events):
            self.playing = False
            self.play_button.configure(text="Replay")
            self.event_index = 0
            return

        event = self.result.events[self.event_index]
        visible_vehicles = self._visible_vehicles()
        self._draw_static_scene()
        self._draw_vehicles(visible_vehicles)
        self._draw_lost_sale_count(visible_vehicles)
        self._draw_clock(event.time, event.queue_length)
        self._write_log(f"{event.time:6.1f} min | Vehicle {event.vehicle_id:03d} | {event.message}\n")
        self.event_index += 1
        delay = max(80, int(650 / self.speed.get()))
        self.after_id = self.after(delay, self._advance_event)

    def _visible_vehicles(self) -> dict[int, str]:
        if not self.result:
            return {}

        event = self.result.events[self.event_index]
        visible = dict(event.active_vehicles)
        for past_event in self.result.events[: self.event_index + 1]:
            if past_event.stage == "rejected":
                visible[past_event.vehicle_id] = "rejected"
        return visible

    def _draw_static_scene(self):
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 980)
        self.canvas.create_rectangle(0, 0, width, 520, fill="#f8fafc", outline="")
        self.canvas.create_rectangle(40, 260, width - 40, 355, fill="#e2e8f0", outline="#94a3b8", width=2)
        self.canvas.create_line(50, 307, width - 50, 307, fill="#f8fafc", dash=(10, 8), width=3)

        stations = [
            ("Arrival", 100, 205, "#dbeafe"),
            ("Order", 350, 155, "#dcfce7"),
            ("Payment", 600, 155, "#fef3c7"),
            ("Pickup", 820, 155, "#fee2e2"),
            ("Exit", 960, 205, "#e2e8f0"),
        ]
        for label, x, y, color in stations:
            self.canvas.create_rectangle(x - 56, y - 34, x + 56, y + 34, fill=color, outline="#334155", width=2)
            self.canvas.create_text(x, y, text=label, font=("Segoe UI", 11, "bold"), fill="#0f172a")

        self.canvas.create_text(100, 385, text="FIFO Queue", font=("Segoe UI", 10, "bold"), fill="#334155")
        self.canvas.create_text(960, 485, text="Full Lane / Lost Sale", font=("Segoe UI", 10, "bold"), fill="#7f1d1d")

    def _draw_vehicles(self, active_vehicles: dict[int, str]):
        occupied: dict[str, int] = {}
        for vehicle_id, stage in sorted(active_vehicles.items()):
            base_x, base_y = STAGE_POSITIONS.get(stage, STAGE_POSITIONS["queue"])
            offset = occupied.get(stage, 0)
            occupied[stage] = offset + 1

            if stage == "rejected":
                x = base_x - (offset % 8) * 28
                y = base_y + (offset // 8) * 28
            elif "waiting" in stage or stage == "queue":
                x = base_x - min(offset, 8) * 26
                y = base_y + (offset // 9) * 28
            else:
                x = base_x + (offset % 3) * 24
                y = base_y + (offset // 9) * 28
            color = CAR_COLORS.get(stage, "#475569")

            self.canvas.create_rectangle(x - 18, y - 10, x + 18, y + 10, fill=color, outline="#0f172a", width=1)
            self.canvas.create_oval(x - 14, y + 7, x - 6, y + 15, fill="#0f172a", outline="")
            self.canvas.create_oval(x + 6, y + 7, x + 14, y + 15, fill="#0f172a", outline="")
            self.canvas.create_text(x, y - 22, text=str(vehicle_id), font=("Segoe UI", 8), fill="#0f172a")

    def _draw_lost_sale_count(self, visible_vehicles: dict[int, str]):
        lost_count = sum(1 for stage in visible_vehicles.values() if stage == "rejected")
        self.canvas.create_text(
            960,
            505,
            text=f"Lost vehicles: {lost_count}",
            font=("Segoe UI", 9, "bold"),
            fill="#7f1d1d",
        )

    def _draw_clock(self, time_value: float, queue_length: int):
        hours = int(time_value // 60)
        minutes = int(time_value % 60)
        self.canvas.create_rectangle(28, 22, 300, 84, fill="#ffffff", outline="#cbd5e1")
        self.canvas.create_text(
            48,
            42,
            anchor="w",
            text=f"Simulation time: Day 1, {hours:02d}:{minutes:02d}",
            font=("Segoe UI", 11, "bold"),
        )
        self.canvas.create_text(48, 66, anchor="w", text=f"Vehicles inside lane: {queue_length}", font=("Segoe UI", 10))

    def _update_summary(self):
        if not self.result:
            return
        summary = self.result.summary
        util = self.result.utilization
        config = self.result.config
        self.summary_text.set(
            "Scenario Results\n"
            f"Peak window: {self._format_time(config.peak_start_minute)}-{self._format_time(config.peak_end_minute)}\n"
            f"Served: {summary['vehicles_served']}\n"
            f"Rejected: {summary['vehicles_rejected']}\n"
            f"Throughput: {summary['throughput_per_hour']:.1f} vehicles/hour\n"
            f"Avg queue wait: {summary['average_queue_wait']:.2f} min\n"
            f"Avg system time: {summary['average_system_time']:.2f} min\n"
            f"Bottleneck: {str(summary['bottleneck']).title()}\n\n"
            "Utilization\n"
            f"Order: {util['order'] * 100:.1f}%\n"
            f"Payment: {util['payment'] * 100:.1f}%\n"
            f"Pickup: {util['pickup'] * 100:.1f}%"
        )

    def _update_analysis(self):
        if not self.result:
            return

        summary = self.result.summary
        util = self.result.utilization
        config = self.result.config
        avg_wait = float(summary["average_queue_wait"])
        avg_system = float(summary["average_system_time"])
        rejected = int(summary["vehicles_rejected"])
        served = int(summary["vehicles_served"])
        generated = int(summary["vehicles_generated"])
        bottleneck = str(summary["bottleneck"])
        acceptance_rate = float(summary["acceptance_rate"])
        max_util_stage = max(util, key=util.get)
        max_util = util[max_util_stage] * 100
        stage_waits = {
            stage: (sum(values) / len(values)) if values else 0.0
            for stage, values in self.result.stage_waits.items()
        }

        issues: list[str] = []
        suggestions: list[str] = []

        if rejected > 0:
            issues.append(
                f"{rejected} vehicle(s) could not enter because the lane reached its capacity."
            )
            suggestions.append(
                "Increase lane capacity, add a waiting bay, or reduce arrival pressure during peak hours."
            )

        if avg_wait > 5:
            issues.append(f"Average queue waiting time is high at {avg_wait:.2f} minutes.")
        elif avg_wait > 3:
            issues.append(f"Average queue waiting time is moderate at {avg_wait:.2f} minutes.")

        if avg_system > 9:
            issues.append(f"Customers spend too long in the system at {avg_system:.2f} minutes on average.")
        elif avg_system > 6:
            issues.append(f"Total system time is acceptable but can still be improved at {avg_system:.2f} minutes.")

        if max_util > 90:
            issues.append(f"The {max_util_stage} resource is overworked at {max_util:.1f}% utilization.")
            suggestions.append(self._resource_suggestion(max_util_stage))
        elif max_util < 35 and served > 0:
            issues.append(f"Resource utilization is low; the busiest stage is only {max_util:.1f}% utilized.")
            suggestions.append("The current setup may be overstaffed for this demand level.")

        if bottleneck != "none" and stage_waits.get(bottleneck, 0.0) > 1:
            suggestions.append(self._resource_suggestion(bottleneck))

        if not issues:
            verdict = "GOOD SCENARIO"
            conclusion = (
                "The drive-thru setup is performing well. Waiting time is low, vehicles are being served, "
                "and no major congestion is shown by this run."
            )
        elif rejected == 0 and avg_wait <= 5 and avg_system <= 9:
            verdict = "ACCEPTABLE SCENARIO"
            conclusion = (
                "The drive-thru can handle the demand, but there is room to improve customer experience "
                "and reduce pressure on the busiest service stage."
            )
        else:
            verdict = "NEEDS IMPROVEMENT"
            conclusion = (
                "This scenario may hurt real-world drive-thru performance because customers wait too long "
                "or the lane becomes congested."
            )

        if not suggestions:
            suggestions.append("Keep the current resource setup and monitor performance during higher demand.")

        analysis = (
            f"{verdict}\n\n"
            f"Conclusion:\n{conclusion}\n\n"
            f"Key findings:\n"
            f"- Demand generated: {generated} vehicle(s)\n"
            f"- Served: {served} vehicle(s)\n"
            f"- Acceptance rate: {acceptance_rate:.1f}%\n"
            f"- Peak period: {self._format_time(config.peak_start_minute)} to {self._format_time(config.peak_end_minute)}\n"
            f"- Main bottleneck: {bottleneck.title()}\n"
            f"- Highest utilization: {max_util_stage.title()} at {max_util:.1f}%\n\n"
            f"Observed issues:\n{self._bullet_text(issues)}\n\n"
            f"Recommended improvement:\n{self._bullet_text(suggestions)}"
        )
        self._set_analysis_text(analysis)

    def _resource_suggestion(self, stage: str) -> str:
        suggestions = {
            "order": "Add another order station or assign staff to speed up order taking during peak periods.",
            "payment": "Add a payment window, use faster cashless payment, or assign a dedicated cashier.",
            "pickup": "Improve food preparation coordination or add pickup staff/window capacity during peak demand.",
        }
        return suggestions.get(stage, "Improve the busiest service stage before increasing arrival volume.")

    def _format_time(self, minute_value: int | float) -> str:
        total_minutes = int(minute_value) % 1440
        hour_24 = total_minutes // 60
        minute = total_minutes % 60
        suffix = "AM" if hour_24 < 12 else "PM"
        hour_12 = hour_24 % 12 or 12
        return f"{hour_12}:{minute:02d} {suffix}"

    def _bullet_text(self, items: list[str]) -> str:
        if not items:
            return "- No major issue detected."
        unique_items = list(dict.fromkeys(items))
        return "\n".join(f"- {item}" for item in unique_items)

    def _set_analysis_text(self, text: str):
        self.analysis_box.configure(state="normal")
        self.analysis_box.delete("1.0", "end")
        self.analysis_box.insert("1.0", text)
        self.analysis_box.configure(state="disabled")

    def _write_log(self, text: str, clear: bool = False):
        self.event_log.configure(state="normal")
        if clear:
            self.event_log.delete("1.0", "end")
        if text:
            self.event_log.insert("end", text)
            self.event_log.see("end")
        self.event_log.configure(state="disabled")

    def _cancel_timer(self):
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None


if __name__ == "__main__":
    DriveThruApp().mainloop()
