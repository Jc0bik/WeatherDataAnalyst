import tkinter as tk
from tkinter import ttk
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class WeatherDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("🌤️ Weather Data Analyst Dashboard")
        self.root.geometry("1400x900")
        
        # Wczytaj dostępne miasta
        self.weather_data_dir = Path(__file__).parent / "weather_data"
        self.available_cities = []
        self.load_cities()
        
        if not self.available_cities:
            tk.messagebox.showerror("Błąd", "Nie znaleziono danych pogodowych!")
            return
        
        self.current_data = None
        self.setup_ui()
        self.on_city_changed(None)  # Załaduj pierwsze miasto
    
    def load_cities(self):
        """Załaduj listę dostępnych miast"""
        available_files = sorted(self.weather_data_dir.glob("open_meteo_*.json"))
        for file in available_files:
            city_name = file.stem.replace("open_meteo_", "").replace("_", " ").title()
            if "CLEANED" not in city_name:
                self.available_cities.append((city_name, file))
    
    def setup_ui(self):
        """Stwórz interfejs użytkownika"""
        # Panel górny z wyborem miasta
        top_frame = ttk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top_frame, text="Wybierz miasto:", font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=5)
        
        city_names = [city[0] for city in self.available_cities]
        self.city_var = tk.StringVar(value=city_names[0])
        city_combo = ttk.Combobox(top_frame, textvariable=self.city_var, values=city_names, state="readonly", width=30)
        city_combo.pack(side=tk.LEFT, padx=5)
        city_combo.bind("<<ComboboxSelected>>", self.on_city_changed)
        
        # Panel z metrykami
        metrics_frame = ttk.LabelFrame(self.root, text="📊 Główne Statystyki", padding=10)
        metrics_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.metrics_labels = {}
        metrics = [
            ("Średnia Temperatura (°C)", "temp"),
            ("Min / Max Temperatura (°C)", "temp_range"),
            ("Średnia Wilgotność (%)", "humidity"),
            ("Średnie Zachmurzenie (%)", "cloud"),
            ("Średnia Prędkość Wiatru (km/h)", "wind"),
            ("Suma Opadów (mm)", "precip"),
            ("Okres danych", "date_range")
        ]
        
        for i, (label, key) in enumerate(metrics):
            row = i // 3
            col = i % 3
            frame = ttk.Frame(metrics_frame)
            frame.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
            
            ttk.Label(frame, text=label, font=("Arial", 9)).pack()
            self.metrics_labels[key] = ttk.Label(frame, text="--", font=("Arial", 11, "bold"), foreground="blue")
            self.metrics_labels[key].pack()
        
        # Panel z wykresami
        charts_frame = ttk.LabelFrame(self.root, text="📈 Wykresy", padding=10)
        charts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Notebook z zakładkami dla różnych wykresów
        self.notebook = ttk.Notebook(charts_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Stwórz zakładki dla każdego wykresu
        self.chart_frames = {}
        chart_names = [
            ("Temperatura", "temp_chart"),
            ("Wilgotność", "humidity_chart"),
            ("Zachmurzenie", "cloud_chart"),
            ("Wiatr", "wind_chart"),
            ("Opady", "precip_chart")
        ]
        
        for name, key in chart_names:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=name)
            self.chart_frames[key] = frame
    
    def on_city_changed(self, event):
        """Obsługa zmiany wybranego miasta"""
        city_name = self.city_var.get()
        city_file = next(file for name, file in self.available_cities if name == city_name)
        
        # Wczytaj dane
        try:
            with open(city_file, "r", encoding="utf-8") as f:
                weather_data = json.load(f)
        except Exception as e:
            print(f"Błąd wczytywania danych: {e}")
            return
        
        # Ekstrakcja i konwersja danych
        hourly_data = weather_data.get("hourly", {})
        times = hourly_data.get("time", [])
        temperatures = hourly_data.get("temperature_2m", [])
        humidity = hourly_data.get("relative_humidity_2m", [])
        cloud_cover = hourly_data.get("cloud_cover", [])
        wind_speed = hourly_data.get("wind_speed_10m", [])
        precipitation = hourly_data.get("precipitation", [])
        
        self.current_data = pd.DataFrame({
            "time": pd.to_datetime(times),
            "temperature": temperatures,
            "humidity": humidity,
            "cloud_cover": cloud_cover,
            "wind_speed": wind_speed,
            "precipitation": precipitation
        })
        
        # Zaktualizuj metryki
        self.update_metrics()
        
        # Zaktualizuj wykresy
        self.update_charts()
    
    def update_metrics(self):
        """Zaktualizuj wyświetlane metryki"""
        if self.current_data is None or self.current_data.empty:
            return
        
        df = self.current_data
        
        metrics_data = {
            "temp": f"{df['temperature'].mean():.1f}",
            "temp_range": f"{df['temperature'].min():.1f} / {df['temperature'].max():.1f}",
            "humidity": f"{df['humidity'].mean():.1f}",
            "cloud": f"{df['cloud_cover'].mean():.1f}",
            "wind": f"{df['wind_speed'].mean():.1f}",
            "precip": f"{df['precipitation'].sum():.1f}",
            "date_range": f"{df['time'].min().strftime('%Y-%m-%d')} do {df['time'].max().strftime('%Y-%m-%d')}"
        }
        
        for key, value in metrics_data.items():
            self.metrics_labels[key].config(text=value)
    
    def update_charts(self):
        """Zaktualizuj wszystkie wykresy"""
        if self.current_data is None or self.current_data.empty:
            return
        
        df = self.current_data
        
        # Usuń stare wykresy
        for frame in self.chart_frames.values():
            for widget in frame.winfo_children():
                widget.destroy()
        
        # Wykres temperatury
        self.create_line_chart(
            self.chart_frames["temp_chart"],
            df["time"], df["temperature"],
            "Temperatura (°C)", "Czas", "Temperatura (°C)",
            color="red"
        )
        
        # Wykres wilgotności
        self.create_line_chart(
            self.chart_frames["humidity_chart"],
            df["time"], df["humidity"],
            "Wilgotność (%)", "Czas", "Wilgotność (%)",
            color="blue"
        )
        
        # Wykres zachmurzenia
        self.create_line_chart(
            self.chart_frames["cloud_chart"],
            df["time"], df["cloud_cover"],
            "Zachmurzenie (%)", "Czas", "Zachmurzenie (%)",
            color="gray"
        )
        
        # Wykres wiatru
        self.create_line_chart(
            self.chart_frames["wind_chart"],
            df["time"], df["wind_speed"],
            "Prędkość Wiatru (km/h)", "Czas", "Prędkość (km/h)",
            color="orange"
        )
        
        # Wykres opadów
        self.create_bar_chart(
            self.chart_frames["precip_chart"],
            df["time"], df["precipitation"],
            "Opady (mm)", "Czas", "Opady (mm)",
            color="steelblue"
        )
    
    def create_line_chart(self, parent_frame, x_data, y_data, title, x_label, y_label, color="blue"):
        """Stwórz i wyświetl wykres liniowy"""
        fig = Figure(figsize=(12, 4), dpi=100)
        ax = fig.add_subplot(111)
        
        ax.plot(x_data, y_data, color=color, linewidth=2, marker='o', markersize=3)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def create_bar_chart(self, parent_frame, x_data, y_data, title, x_label, y_label, color="blue"):
        """Stwórz i wyświetl wykres słupkowy"""
        fig = Figure(figsize=(12, 4), dpi=100)
        ax = fig.add_subplot(111)
        
        ax.bar(x_data, y_data, color=color, alpha=0.7, width=0.02)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, alpha=0.3, axis="y")
        fig.autofmt_xdate()
        
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherDashboard(root)
    root.mainloop()
