import serial
import json
import time
import argparse
import sys
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

# ANSI Color Codes for Terminal Output
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

def classify_state(success_rate):
    """
    Evaluates the success rate and returns a formatted string with the state.
    Thresholds based on empirical physical telemetry:
    - Base Line: > 90%
    - Light Interference: 30% - 90%
    - Medium Interference: > 0% - 30%
    - Critical Block: 0%
    """
    if success_rate > 90:
        return f"{Colors.OKGREEN}ESTADO: Línea Base{Colors.ENDC}"
    elif success_rate > 30:
        return f"{Colors.WARNING}ESTADO: Interrupción Parcial (Posible dedo){Colors.ENDC}"
    elif success_rate > 0:
        return f"{Colors.FAIL}ESTADO: Interferencia Media (4 dedos){Colors.ENDC}"
    else:
        return f"{Colors.BOLD}{Colors.FAIL}ESTADO: Bloqueo Crítico (Palma o Tarjeta Removida){Colors.ENDC}"

# Globals for Plotting Data
max_points = 100
x_data = deque(maxlen=max_points)
y_success = deque(maxlen=max_points)
y_latency = deque(maxlen=max_points)

def parse_args():
    parser = argparse.ArgumentParser(description="NFC Real-time Dashboard with State Machine")
    parser.add_argument("port", help="The serial port to connect to (e.g., /dev/ttyUSB0 or COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    return parser.parse_args()

def init():
    line_success.set_data([], [])
    line_latency.set_data([], [])
    return line_success, line_latency

def update(frame):
    try:
        # Read all available lines in the buffer
        while ser.in_waiting > 0:
            line_str = ser.readline().decode('utf-8').strip()
            if line_str:
                try:
                    data = json.loads(line_str)

                    success_rate = data.get("success_rate_pct", 0)
                    latency = data.get("avg_latency_us", 0)

                    # Print State Machine output to console
                    state_msg = classify_state(success_rate)
                    print(f"Success Rate: {success_rate:5.1f}% | Latency: {latency:6d} us | {state_msg}")

                    # Update deque buffers for plotting
                    current_time = time.time()
                    x_data.append(current_time)
                    y_success.append(success_rate)
                    y_latency.append(latency)

                except json.JSONDecodeError:
                    pass

        # Update plot lines if data exists
        if len(y_success) > 0:
            # We use an index based range for x-axis to keep it simple and scrolling
            x_vals = range(len(y_success))

            line_success.set_data(x_vals, list(y_success))
            line_latency.set_data(x_vals, list(y_latency))

            ax1.set_xlim(0, max_points)
            ax2.set_xlim(0, max_points)

            if len(y_latency) > 0:
                max_lat = max(y_latency)
                ax2.set_ylim(0, (max_lat * 1.2) if max_lat > 0 else 1000)

    except serial.SerialException:
        print(f"{Colors.FAIL}Conexión serie perdida. El dispositivo puede haber sido desconectado.{Colors.ENDC}")
        sys.exit(1)

    return line_success, line_latency

if __name__ == "__main__":
    args = parse_args()

    try:
        global ser
        ser = serial.Serial(args.port, args.baud, timeout=0.1)
        print(f"{Colors.OKCYAN}Conectado a {args.port} a {args.baud} baudios.{Colors.ENDC}")
        print(f"{Colors.OKCYAN}Iniciando Motor de Clasificación de Estados y Gráficas en Tiempo Real...{Colors.ENDC}")
    except serial.SerialException as e:
        print(f"{Colors.FAIL}No se pudo abrir el puerto serie {args.port}: {e}{Colors.ENDC}")
        sys.exit(1)

    # Setup Matplotlib Figure and Axes
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.canvas.manager.set_window_title('NFC Spectroscopy Real-time Dashboard')
    fig.suptitle('Motor de Clasificación de Estados en Tiempo Real', fontsize=16)

    ax1.set_title('Tasa de Éxito de Lectura (Success Rate %)')
    ax1.set_ylim(-5, 105)
    ax1.set_ylabel('%')
    ax1.grid(True, linestyle='--', alpha=0.7)
    line_success, = ax1.plot([], [], 'g-', lw=2)

    ax2.set_title('Latencia Promedio de Respuesta (us)')
    ax2.set_ylabel('Microsegundos')
    ax2.grid(True, linestyle='--', alpha=0.7)
    line_latency, = ax2.plot([], [], 'b-', lw=2)

    # Use FuncAnimation for real-time plot updates
    ani = FuncAnimation(fig, update, init_func=init, interval=100, blit=False, cache_frame_data=False)

    try:
        plt.show()
    except KeyboardInterrupt:
        print(f"\n{Colors.OKBLUE}Cerrando Dashboard...{Colors.ENDC}")
    finally:
        if 'ser' in globals() and ser.is_open:
            ser.close()
