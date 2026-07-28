import serial
import json
import time
import sys
import argparse
import numpy as np
import pandas as pd
import joblib
from collections import deque

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def run_calibration(ser, duration=10):
    """
    Records ambient electromagnetic noise for 'duration' seconds to establish a baseline.
    Requires the user to place the empty container or sterile barrier (e.g., slide) on the sensor.
    """
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}--- FASE DE CALIBRACIÓN INICIADA ---{Colors.ENDC}")
    print(f"{Colors.WARNING}Por favor, coloque el contenedor vacío o portaobjetos estéril sobre el sensor.{Colors.ENDC}")
    print(f"Calibrando el ruido ambiental durante {duration} segundos...")

    start_time = time.time()
    baseline_latencies = []
    baseline_success = []

    # Flush existing buffer to avoid stale data
    ser.reset_input_buffer()

    while (time.time() - start_time) < duration:
        try:
            line_str = ser.readline().decode('utf-8').strip()
            if line_str:
                data = json.loads(line_str)
                baseline_success.append(data.get("success_rate_pct", 0))
                baseline_latencies.append(data.get("avg_latency_us", 0))

                # Visual feedback during calibration
                elapsed = time.time() - start_time
                sys.stdout.write(f"\rProgreso: [{int(elapsed)}/{duration}s] ...")
                sys.stdout.flush()
        except json.JSONDecodeError:
            pass
        except serial.SerialException as e:
             print(f"\n{Colors.FAIL}Error de lectura serial durante la calibración: {e}{Colors.ENDC}")
             sys.exit(1)

    if not baseline_latencies or not baseline_success:
        print(f"\n{Colors.FAIL}Error: No se recibieron datos del sensor durante la calibración. Verifique la conexión SPI/RC522.{Colors.ENDC}")
        sys.exit(1)

    base_lat_mean = np.mean(baseline_latencies)
    base_sr_mean = np.mean(baseline_success)

    print(f"\n{Colors.OKGREEN}Calibración Completada.{Colors.ENDC}")
    print(f"Línea Base -> Éxito Medio: {base_sr_mean:.1f}% | Latencia Media: {base_lat_mean:.1f}us")
    return base_sr_mean, base_lat_mean

def extract_live_features(window_df, base_sr, base_lat):
    """
    Extracts sliding window features identically to the training pipeline.

    Note: The current model was trained on absolute telemetry values.
    To fully utilize the baseline calibration offsets, the training
    pipeline must be retrained on (value - baseline) deltas. Currently,
    the baseline is captured for environmental logging but not subtracted
    to prevent feature space mismatch with the pre-trained model.
    """
    success_rates = window_df['success_rate_pct'].values
    latencies = window_df['avg_latency_us'].values
    window_size = len(window_df)

    # Feature: Success Rate Drop metrics
    sr_mean = np.mean(success_rates)
    sr_min = np.min(success_rates)
    sr_var = np.var(success_rates)

    # Feature: Latency metrics
    lat_mean = np.mean(latencies)
    lat_max = np.max(latencies)
    lat_var = np.var(latencies)

    # Feature: Latency Decay Slope (Linear regression slope over time)
    x = np.arange(window_size)
    if len(set(latencies)) > 1: # Avoid polyfit warnings on flat data
        slope, _ = np.polyfit(x, latencies, 1)
    else:
        slope = 0.0

    features = {
        'sr_mean': sr_mean,
        'sr_min': sr_min,
        'sr_var': sr_var,
        'lat_mean': lat_mean,
        'lat_max': lat_max,
        'lat_var': lat_var,
        'lat_slope': slope
    }

    return pd.DataFrame([features])

def main():
    parser = argparse.ArgumentParser(description="Live ML Inference for Dielectric Spectroscopy")
    parser.add_argument("port", help="Puerto serie (ej. /dev/ttyUSB0 o COM3)")
    parser.add_argument("--model", default="nfc_dielectric_model.pkl", help="Ruta al modelo entrenado .pkl")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--window", type=int, default=5, help="Tamaño de ventana deslizante en segundos/muestras")
    args = parser.parse_args()

    print(f"{Colors.HEADER}Cargando modelo ML desde {args.model}...{Colors.ENDC}")
    try:
        clf = joblib.load(args.model)
    except FileNotFoundError:
        print(f"{Colors.FAIL}Error: No se encontró el modelo {args.model}. Ejecute ml_pipeline.py primero.{Colors.ENDC}")
        sys.exit(1)

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
        print(f"{Colors.OKGREEN}Conectado exitosamente a {args.port}.{Colors.ENDC}")
    except serial.SerialException as e:
        print(f"{Colors.FAIL}No se pudo abrir el puerto serie {args.port}: {e}{Colors.ENDC}")
        sys.exit(1)

    # Phase 1: Calibration
    try:
        base_sr_mean, base_lat_mean = run_calibration(ser, duration=10)
    except KeyboardInterrupt:
        print("\nCalibración cancelada por el usuario.")
        sys.exit(0)

    print(f"\n{Colors.OKCYAN}{Colors.BOLD}--- INICIANDO INFERENCIA EN VIVO ---{Colors.ENDC}")
    print("Coloque la muestra a analizar sobre el sensor. Analizando firma electromagnética...\n")

    # Data structures for sliding window
    window_data = deque(maxlen=args.window)

    ser.reset_input_buffer()

    try:
        while True:
            try:
                line_str = ser.readline().decode('utf-8').strip()
                if line_str:
                    data = json.loads(line_str)

                    # Append new data point to sliding window
                    window_data.append({
                        'success_rate_pct': data.get("success_rate_pct", 0),
                        'avg_latency_us': data.get("avg_latency_us", 0)
                    })

                    # Only predict when the window is completely full
                    if len(window_data) == args.window:
                        df_window = pd.DataFrame(list(window_data))

                        # Extract features and apply calibration offsets if needed by the logic
                        # (Currently the training pipeline uses absolute values. If you retrain
                        # using baseline-delta values, apply the subtraction here).
                        X_live = extract_live_features(df_window, base_sr_mean, base_lat_mean)

                        # Inference
                        prediction = clf.predict(X_live)[0]
                        probabilities = clf.predict_proba(X_live)[0]
                        confidence = np.max(probabilities) * 100

                        # Console Output
                        if confidence > 85:
                            color = Colors.OKGREEN
                        elif confidence > 60:
                            color = Colors.WARNING
                        else:
                            color = Colors.FAIL

                        sys.stdout.write(f"\r{Colors.BOLD}Predicción actual:{Colors.ENDC} {color}{prediction} ({confidence:.1f}% de confianza){Colors.ENDC} | Latencia: {data.get('avg_latency_us')} us   ")
                        sys.stdout.flush()

            except json.JSONDecodeError:
                pass # Ignore malformed json lines from ESP32 glitches
            except serial.SerialException as e:
                print(f"\n{Colors.FAIL}Error crítico de comunicación SPI/Serial: {e}. ¿Se desconectó el ESP32?{Colors.ENDC}")
                break

    except KeyboardInterrupt:
         print(f"\n\n{Colors.OKBLUE}Deteniendo inferencia en vivo. Cerrando puerto...{Colors.ENDC}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
