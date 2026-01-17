import tkinter as tk
from tkinter import ttk, messagebox
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import subprocess
import sys
from weatherDataAnalyst import calculate_all_rankings

class WeatherDashboard:
    def __init__(self, root):
        # Wczytaj słownik tłumaczeń miast/krajów
        try:
            with open(Path(__file__).parent / "pl_cities_countries.json", "r", encoding="utf-8") as f:
                self.pl_dict = json.load(f)
        except Exception:
            self.pl_dict = {}
        self.root = root
        self.root.title("Weather Data Analyst Dashboard")
        self.root.geometry("1400x900")
        
        # Zapisz czas uruchomienia programu
        self.start_time = datetime.now()
        
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
        
        # Auto-refresh danych przy uruchomieniu (ale DOPIERO po załadowaniu UI)
        # Opóźnij o 500ms aby UI się załadował
        self.root.after(500, self.auto_download_data)
    
    def load_cities(self):
        """Załaduj listę dostępnych miast"""
        available_files = sorted(self.weather_data_dir.glob("open_meteo_*.json"))
        for file in available_files:
            city_name = file.stem.replace("open_meteo_", "").replace("_", " ").title()
            # Pomijaj "All Capitals" warianty i "Cleaned"
            if "cleaned" not in city_name.lower() and "all capitals" not in city_name.lower():
                pl_city = self.pl_dict.get(city_name, city_name)
                self.available_cities.append((pl_city, file, city_name))  # (PL, file, EN)
    
    def setup_ui(self):
        """Stwórz interfejs użytkownika"""
        # Zainicjalizuj słownik dla chart frames
        self.chart_frames = {}
        self.metrics_labels = {}
        
        # GŁÓWNY NOTEBOOK - Ranking klimatyczny | Pogoda (na górnym poziomie)
        main_notebook = ttk.Notebook(self.root)
        main_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ========== ZAKŁADKA 1: RANKING KLIMATYCZNY ==========
        ranking_frame = ttk.Frame(main_notebook)
        main_notebook.add(ranking_frame, text="Ranking klimatyczny")
        self.chart_frames["ranking_chart"] = ranking_frame
        
        # ========== ZAKŁADKA 2: POGODA ==========
        weather_frame = ttk.Frame(main_notebook)
        main_notebook.add(weather_frame, text="Pogoda")
        
        # Panel górny z wyborem miasta - w POGODA
        top_frame = ttk.Frame(weather_frame)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top_frame, text="Wybierz miasto:", font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=5)
        
        city_names = [city[0] for city in self.available_cities]
        # Dodaj opcję "Wszystkie stolice" na początku
        city_names = ["Wszystkie stolice"] + city_names
        self.city_var = tk.StringVar(value=city_names[1])
        self.city_combo = ttk.Combobox(top_frame, textvariable=self.city_var, values=city_names, state="readonly", width=30)
        self.city_combo.pack(side=tk.LEFT, padx=5)
        self.city_combo.bind("<<ComboboxSelected>>", self.on_city_changed)
        
        # Selektor okresu
        ttk.Label(top_frame, text="Okres:", font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=20)
        
        period_options = ["24h", "3 dni", "7 dni", "16 dni"]
        self.period_var = tk.StringVar(value="16 dni")
        period_combo = ttk.Combobox(top_frame, textvariable=self.period_var, values=period_options, state="readonly", width=15)
        period_combo.pack(side=tk.LEFT, padx=5)
        period_combo.bind("<<ComboboxSelected>>", self.on_period_changed)
        
        # Przycisk pobierania danych
        self.download_btn = ttk.Button(top_frame, text="Pobierz nowe dane", command=self.on_download_data)
        self.download_btn.pack(side=tk.LEFT, padx=20)
        
        # Panel z metrykami
        metrics_frame = ttk.LabelFrame(weather_frame, text="Główne Statystyki", padding=10)
        metrics_frame.pack(fill=tk.X, padx=10, pady=10)
        
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
        charts_container_frame = ttk.LabelFrame(weather_frame, text="Wykresy", padding=10)
        charts_container_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Notebook z wykresami dla konkretnego miasta
        self.notebook = ttk.Notebook(charts_container_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Stwórz zakładki dla każdego wykresu
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
        
        # Obsługa "Wszystkie stolice" - średnia z wszystkich miast
        if city_name == "Wszystkie stolice":
            self._load_all_capitals_data()
            return
        
        # Pobierz oryginalną nazwę angielską na podstawie polskiej
        city_file = None
        for pl_name, file, en_name in self.available_cities:
            if pl_name == city_name:
                city_file = file
                break
        if not city_file:
            return
        
        # Wczytaj dane
        try:
            with open(city_file, "r", encoding="utf-8") as f:
                weather_data = json.load(f)
        except Exception as e:
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
            "temperature_2m": temperatures,
            "relative_humidity_2m": humidity,
            "cloud_cover": cloud_cover,
            "wind_speed_10m": wind_speed,
            "precipitation": precipitation
        })
        
        # Zaktualizuj metryki
        self.update_metrics()
        
        # Zaktualizuj wykresy
        self.update_charts()
    
    def _load_all_capitals_data(self):
        """Przygotuj średnią z wszystkich miast z CLEANED pliku - w strefie Warszawy"""
        try:
            cleaned_file = self.weather_data_dir / "open_meteo_all_capitals_CLEANED.json"
            with open(cleaned_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            self.current_data = None
            return
        
        
        # Przygotuj dane do analizy
        rows = []
        for city_block in raw.get("capitals_weather_cleaned", []):
            city_name = city_block.get("metadata", {}).get("city", "Unknown")
            city_tz = city_block.get("metadata", {}).get("timezone", "Europe/Warsaw")
            for row in city_block.get("cleaned_hourly_rows", []):
                rows.append({
                    "time": row["time"],
                    "city": city_name,
                    "timezone": city_tz,
                    "temperature_2m": row["temperature_2m"],
                    "relative_humidity_2m": row["relative_humidity_2m"],
                    "cloud_cover": row["cloud_cover"],
                    "wind_speed_10m": row["wind_speed_10m"],
                    "precipitation": row["precipitation"],
                })
        
        if not rows:
            self.current_data = None
            return
        
        
        # Stwórz DataFrame
        df = pd.DataFrame(rows)
        
        # Konwertuj czas - dane są w lokalnej strefie każdego miasta
        try:
            df["time_warsaw"] = df.apply(
                lambda row: pd.to_datetime(row["time"]).tz_localize(row["timezone"]).tz_convert("Europe/Warsaw"),
                axis=1
            )
        except Exception as e:
            self.current_data = None
            return
        
        # Ogranicz do daty gdy wszystkie (europejskie) miasta mają dane: do 2026-02-01 23:00 Warszawa
        max_common_date = pd.Timestamp("2026-02-01 23:00", tz="Europe/Warsaw")
        df = df[df["time_warsaw"] <= max_common_date]
        
        
        # Pogrupuj po godzinie (w strefie Warszawy) i oblicz średnią
        self.current_data = df.groupby("time_warsaw").agg({
            "temperature_2m": "mean",
            "relative_humidity_2m": "mean",
            "cloud_cover": "mean",
            "wind_speed_10m": "mean",
            "precipitation": "mean"
        }).reset_index()
        
        # Przełącz nazwy kolumn
        self.current_data = self.current_data.rename(columns={"time_warsaw": "time"})
        
        # Konwertuj do naiwnych datetime (bez timezone info)
        self.current_data["time"] = self.current_data["time"].dt.tz_localize(None).astype("datetime64[ns]")
        
        
        # Zaktualizuj metryki i wykresy
        self.update_metrics()
        self.update_charts()
        
    
    def on_period_changed(self, event):
        """Obsługa zmiany wybranego okresu"""
        if self.current_data is not None:
            self.update_metrics()
            self.update_charts()
    
    def auto_download_data(self):
        """Uruchom pobieranie danych w osobnym wątku (przy starcie)"""
        import threading
        thread = threading.Thread(target=self.on_download_data, daemon=True)
        thread.start()
    
    def on_download_data(self):
        """Pobierz i analizuj świeże dane pogodowe"""
        self.download_btn.config(state="disabled", text="Pobieranie...")
        self.root.update()
        
        try:
            # Uruchom weatherDataCollector
            result = subprocess.run(
                [sys.executable, "weatherDataCollector.py"],
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                messagebox.showinfo("Sukces", "Dane pogodowe pobrane i przeanalizowane!")
                
                # Aktualizuj czas początkowy
                self.start_time = datetime.now()
                
                # Przeładuj dostępne miasta
                self.available_cities = []
                self.load_cities()
                
                # Aktualizuj combobox
                city_names = [city[0] for city in self.available_cities]
                city_names = ["Wszystkie stolice"] + city_names
                self.city_combo["values"] = city_names
                
                # Przeładuj dane dla obecnie wybranego miasta
                current_city = self.city_var.get()
                if current_city not in city_names:
                    self.city_var.set(city_names[1])  # Ustaw drugie miasto (pierwsze normalne)
                
                self.on_city_changed(None)
                
                # Odśwież ranking
                self.show_ranking()
            else:
                messagebox.showerror("Błąd", f"Nie udało się pobrać danych:\n{result.stderr}")
        
        except subprocess.TimeoutExpired:
            messagebox.showerror("Błąd", "Pobieranie danych trwało zbyt długo!")
        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd podczas pobierania danych:\n{str(e)}")
        finally:
            self.download_btn.config(state="normal", text="Pobierz nowe dane")
    
    def get_filtered_data(self):
        """Zwróć dane przefiltrowane wg wybranego okresu - od teraz do przodu"""
        if self.current_data is None or self.current_data.empty:
            return None
        
        df = self.current_data.copy()
        df = df.sort_values("time")
        period = self.period_var.get()
        
        # Punkt startu: bieżący czas uruchomienia programu
        start_date = self.start_time
        
        # Punkt końca: od startu + okres
        if period == "24h":
            end_date = start_date + timedelta(hours=24)
        elif period == "3 dni":
            end_date = start_date + timedelta(days=3)
        elif period == "7 dni":
            end_date = start_date + timedelta(days=7)
        else:  # "16 dni"
            end_date = start_date + timedelta(days=16)
        
        # Filtruj dane: od start_date do end_date (włącznie)
        filtered_df = df[(df["time"] >= start_date) & (df["time"] <= end_date)]
        
        # Jeśli brak danych w tym przedziale, zwróć dostępne dane od startu
        if filtered_df.empty:
            filtered_df = df[df["time"] >= start_date]
        
        return filtered_df
    
    def show_ranking(self):
        """Pokaż ranking klimatyczny wszystkich miast"""
        try:
            # Oblicz wszystkie rankingi
            cleaned_file = str(self.weather_data_dir / "open_meteo_all_capitals_CLEANED.json")
            rankings_data = calculate_all_rankings(cleaned_file)
        except Exception as e:
            return
        
        # Pokaż ranking w zakładce
        ranking_frame = self.chart_frames.get("ranking_chart")
        if ranking_frame:
            # Wyczyść zawartość
            for widget in ranking_frame.winfo_children():
                widget.destroy()
            
            # Stwórz Notebook z różnymi rankingami
            ranking_notebook = ttk.Notebook(ranking_frame)
            ranking_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # TAB 1: Główny ranking
            tab1 = ttk.Frame(ranking_notebook)
            ranking_notebook.add(tab1, text="Ranking ogólny")
            
            desc_frame = ttk.Frame(tab1)
            desc_frame.pack(fill=tk.X, padx=10, pady=10)
            desc_text = "Oto ranking klimatyczny na podstawie danych zebranych z okresu 16 dni. 1 miejsce oznacza najprzyjemniejszy dla człowieka klimat, a 15 najmniej przyjemny."
            ttk.Label(desc_frame, text=desc_text, font=("Arial", 10), wraplength=600, justify=tk.LEFT).pack(anchor=tk.W)
            
            # Tłumaczenie miast w rankingu ogólnym
            ranking_df = rankings_data["ranking"].copy()
            if "Miasto" in ranking_df.columns:
                ranking_df["Miasto"] = ranking_df["Miasto"].map(lambda x: self.pl_dict.get(x, x))
            self._create_treeview(tab1, ranking_df, list(ranking_df.columns))
            
            # TAB 2: Statystyki pogodowe
            tab2 = ttk.Frame(ranking_notebook)
            ranking_notebook.add(tab2, text="Statystyki pogodowe")
            desc2 = ttk.Label(tab2, text="Podsumowanie uśrednionych statystyk dla całego badanego okresu.", font=("Arial", 10), wraplength=700, justify=tk.LEFT)
            desc2.pack(anchor=tk.W, padx=10, pady=(10,0))
            # Polskie tłumaczenia miast i krajów
            import json
            try:
                with open("pl_cities_countries.json", "r", encoding="utf-8") as f:
                    pl_dict = json.load(f)
            except Exception:
                pl_dict = {}
            stats_df = rankings_data["city_stats"].copy()
            stats_df["Kraj"] = stats_df["country"].map(lambda x: pl_dict.get(x, x))
            stats_df["Miasto"] = stats_df["city"].map(lambda x: pl_dict.get(x, x))
            stats_df = stats_df.rename(columns={
                "avg_temperature": "Śr. temp.",
                "max_temperature": "Max temp.",
                "avg_humidity": "Śr. wilgotność",
                "max_humidity": "Max wilgotność",
                "min_humidity": "Min wilgotność",
                "avg_wind": "Śr. prędkość wiatru",
                "max_wind": "Max prędkość wiatru",
                "avg_precipitation": "Śr. opady",
                "total_precipitation": "Suma opadów",
                "avg_clouds": "Śr. zachmurzenie"
            })
            stats_cols = [
                "Kraj", "Miasto", "Śr. temp.", "Max temp.",
                "Śr. wilgotność", "Max wilgotność", "Min wilgotność",
                "Śr. prędkość wiatru", "Max prędkość wiatru",
                "Śr. opady", "Suma opadów", "Śr. zachmurzenie"
            ]
            stats_df = stats_df[stats_cols]
            units_row = {
                "Kraj": "",
                "Miasto": "",
                "Śr. temp.": "°C",
                "Max temp.": "°C",
                "Śr. wilgotność": "%",
                "Max wilgotność": "%",
                "Min wilgotność": "%",
                "Śr. prędkość wiatru": "km/h",
                "Max prędkość wiatru": "km/h",
                "Śr. opady": "mm",
                "Suma opadów": "mm",
                "Śr. zachmurzenie": "%"
            }
            stats_df = pd.concat([stats_df, pd.DataFrame([units_row])], ignore_index=True)
            self._create_treeview(tab2, stats_df, stats_cols)

            # TAB 3: Top 3 miasta na dzień (z wyborem daty)
            tab3 = ttk.Frame(ranking_notebook)
            ranking_notebook.add(tab3, text="Top 3 na dzień")
            desc3 = ttk.Label(tab3, text="Ranking top 3 miast pod względem klimatu dla wybranej daty.", font=("Arial", 10), wraplength=700, justify=tk.LEFT)
            desc3.pack(anchor=tk.W, padx=10, pady=(10,0))
            # Wybór daty
            dates = sorted(rankings_data["top3_per_day"]["Data"].unique())
            date_var = tk.StringVar(value=dates[0] if dates else "")
            date_frame = ttk.Frame(tab3)
            date_frame.pack(anchor=tk.W, padx=10, pady=(10,0))
            ttk.Label(date_frame, text="Wybierz datę:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
            date_combo = ttk.Combobox(date_frame, textvariable=date_var, values=dates, state="readonly", width=15)
            date_combo.pack(side=tk.LEFT, padx=5)
            # Tabela wyników
            tree_frame = ttk.Frame(tab3)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            def update_top3_table(*args):
                for widget in tree_frame.winfo_children():
                    widget.destroy()
                filtered = rankings_data["top3_per_day"][rankings_data["top3_per_day"]["Data"] == date_var.get()]
                # Polskie tłumaczenia
                filtered = filtered.copy()
                filtered["Miasto"] = filtered["Miasto"].map(lambda x: pl_dict.get(x, x))
                self._create_treeview(tree_frame, filtered, list(filtered.columns))
                # Adnotacja dla ostatniego dnia i dla dni z <3 miastami
                if date_var.get() == dates[-1] or len(filtered) < 3:
                    ttk.Label(tree_frame, text="Uwaga: dla tej daty dostępne są dane tylko z części miast (ograniczenie stref czasowych)", font=("Arial", 9, "italic"), foreground="red").pack(anchor=tk.W, padx=5, pady=5)
            date_var.trace_add("write", lambda *a: update_top3_table())
            update_top3_table()

            # TAB 4: Top1 dnia (best_city_per_day)
            tab4 = ttk.Frame(ranking_notebook)
            ranking_notebook.add(tab4, text="Top1 dnia")
            desc4 = ttk.Label(tab4, text="Najlepszy dzień poszczególnych dni badanego okresu.", font=("Arial", 10), wraplength=700, justify=tk.LEFT)
            desc4.pack(anchor=tk.W, padx=10, pady=(10,0))
            # Polskie tłumaczenia
            best_df = rankings_data["best_city_per_day"].copy()
            best_df["Miasto"] = best_df["Miasto"].map(lambda x: pl_dict.get(x, x))
            self._create_treeview(tab4, best_df, list(best_df.columns))
            # Adnotacja dla ostatniego dnia
            if len(best_df) > 0:
                last_day = best_df["Data"].iloc[-1]
                ttk.Label(tab4, text=f"Uwaga: dla ostatniego dnia dostępne są dane tylko z dwóch miast (ograniczenie stref czasowych)", font=("Arial", 9, "italic"), foreground="red").pack(anchor=tk.W, padx=5, pady=5)
    
    def _create_treeview(self, parent_frame, dataframe, columns):
        """Stwórz Treeview z danymi z DataFrame"""
        tree = ttk.Treeview(parent_frame, columns=columns, height=25)
        tree.column("#0", width=0, stretch=tk.NO)
        
        # Ustaw nagłówki
        for col in columns:
            tree.column(col, anchor=tk.CENTER, width=100)
            tree.heading(col, text=col)
        
        # Dodaj wiersze
        for idx, row in dataframe.iterrows():
            values = [str(row[col]) for col in columns]
            tree.insert(parent='', index='end', iid=idx, text='', values=values)
        
        # Dodaj scrollbar
        scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        
        tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def update_metrics(self):
        """Zaktualizuj wyświetlane metryki"""
        if self.current_data is None or self.current_data.empty:
            for key in self.metrics_labels:
                self.metrics_labels[key].config(text="--")
            return
        
        df = self.get_filtered_data()
        
        if df is None or df.empty:
            for key in self.metrics_labels:
                self.metrics_labels[key].config(text="--")
            return
        
        metrics_data = {
            "temp": f"{df['temperature_2m'].mean():.1f}",
            "temp_range": f"{df['temperature_2m'].min():.1f} / {df['temperature_2m'].max():.1f}",
            "humidity": f"{df['relative_humidity_2m'].mean():.1f}",
            "cloud": f"{df['cloud_cover'].mean():.1f}",
            "wind": f"{df['wind_speed_10m'].mean():.1f}",
            "precip": f"{df['precipitation'].sum():.1f}",
            "date_range": f"{df['time'].min().strftime('%Y-%m-%d')} do {df['time'].max().strftime('%Y-%m-%d')}"
        }
        
        for key, value in metrics_data.items():
            self.metrics_labels[key].config(text=value)
    
    def update_charts(self):
        """Zaktualizuj wszystkie wykresy"""
        if self.current_data is None or self.current_data.empty:
            return
        
        df = self.get_filtered_data()
        is_24h = self.period_var.get() == "24h"
        
        # Usuń stare wykresy (nie ranking_chart)
        for key in ["temp_chart", "humidity_chart", "cloud_chart", "wind_chart", "precip_chart"]:
            frame = self.chart_frames[key]
            for widget in frame.winfo_children():
                widget.destroy()
        
        # Wykres temperatury
        self.create_line_chart(
            self.chart_frames["temp_chart"],
            df["time"], df["temperature_2m"],
            "Temperatura (°C)", "Czas", "Temperatura (°C)",
            color="red", is_24h=is_24h
        )
        
        # Wykres wilgotności
        self.create_line_chart(
            self.chart_frames["humidity_chart"],
            df["time"], df["relative_humidity_2m"],
            "Wilgotność (%)", "Czas", "Wilgotność (%)",
            color="blue", is_24h=is_24h
        )
        
        # Wykres zachmurzenia
        self.create_line_chart(
            self.chart_frames["cloud_chart"],
            df["time"], df["cloud_cover"],
            "Zachmurzenie (%)", "Czas", "Zachmurzenie (%)",
            color="gray", is_24h=is_24h
        )
        
        # Wykres wiatru
        self.create_line_chart(
            self.chart_frames["wind_chart"],
            df["time"], df["wind_speed_10m"],
            "Prędkość Wiatru (km/h)", "Czas", "Prędkość (km/h)",
            color="orange", is_24h=is_24h
        )
        
        # Wykres opadów
        self.create_bar_chart(
            self.chart_frames["precip_chart"],
            df["time"], df["precipitation"],
            "Opady (mm)", "Czas", "Opady (mm)",
            color="steelblue", is_24h=is_24h
        )
    
    def create_line_chart(self, parent_frame, x_data, y_data, title, x_label, y_label, color="blue", is_24h=True):
        """Stwórz i wyświetl wykres liniowy"""
        fig = Figure(figsize=(12, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        ax.plot(x_data, y_data, color=color, linewidth=2, marker='o', markersize=3)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, alpha=0.3)
        
        # Pokaż etykiety dat na osi X
        x_list = list(x_data)
        if is_24h:
            # Dla 24h pokaż wszystkie godziny
            ax.set_xticks(x_data)
            x_labels = [d.strftime('%Y-%m-%d %H:%M') if hasattr(d, 'strftime') else str(d) for d in x_data]
            ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)
        else:
            # Dla dłuższych okresów pokaż co 24 godziny (co dzień)
            tick_indices = list(range(0, len(x_list), 24))
            # Dodaj ostatni punkt tylko jeśli jest wystarczająco daleko od poprzedniego
            if len(tick_indices) > 0 and (len(x_list) - 1 - tick_indices[-1] >= 12):
                tick_indices.append(len(x_list) - 1)
            elif len(tick_indices) == 0:
                tick_indices.append(len(x_list) - 1)
            
            tick_values = [x_list[i] for i in tick_indices if i < len(x_list)]
            ax.set_xticks(tick_values)
            x_labels = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in tick_values]
            ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=9)
        
        # Dostosuj marginesy
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def create_bar_chart(self, parent_frame, x_data, y_data, title, x_label, y_label, color="blue", is_24h=True):
        """Stwórz i wyświetl wykres słupkowy"""
        fig = Figure(figsize=(12, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        # Dla danych czasowych używamy lepszej szerokości słupków
        x_list = list(x_data)
        if len(x_list) > 1:
            time_range = (max(x_list) - min(x_list)).total_seconds() / 86400  # dni
            bar_width = max(0.5, time_range / len(x_list) * 0.8)
        else:
            bar_width = 0.5
        
        ax.bar(x_data, y_data, color=color, alpha=0.7, width=bar_width)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, alpha=0.3, axis="y")
        
        # Pokaż etykiety dat na osi X
        if is_24h:
            # Dla 24h pokaż wszystkie godziny
            ax.set_xticks(x_data)
            x_labels = [d.strftime('%Y-%m-%d %H:%M') if hasattr(d, 'strftime') else str(d) for d in x_data]
            ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)
        else:
            # Dla dłuższych okresów pokaż co 24 godziny (co dzień)
            tick_indices = list(range(0, len(x_list), 24))
            # Dodaj ostatni punkt tylko jeśli jest wystarczająco daleko od poprzedniego
            if len(tick_indices) > 0 and (len(x_list) - 1 - tick_indices[-1] >= 12):
                tick_indices.append(len(x_list) - 1)
            elif len(tick_indices) == 0:
                tick_indices.append(len(x_list) - 1)
            
            tick_values = [x_list[i] for i in tick_indices if i < len(x_list)]
            ax.set_xticks(tick_values)
            x_labels = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in tick_values]
            ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=9)
        
        # Dostosuj marginesy
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherDashboard(root)
    root.mainloop()
