import serial
import json
import csv
import time
import sys
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="ML Labeled Data Collector for Dielectric Spectroscopy")
    parser.add_argument("port", help="The serial port to connect to (e.g., /dev/ttyUSB0 or COM3)")
    parser.add_argument("label", help="The class label for the material currently being measured (e.g., 'water', 'soap_thick', 'baseline')")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--duration", type=int, default=30, help="Duration to record in seconds (default: 30)")
    args = parser.parse_args()

    csv_filename = "ml_training_data.csv"

    # Check if we need to write the header
    write_header = not os.path.exists(csv_filename)

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
        print(f"Connected to {args.port} at {args.baud} baud.")
        print(f"Recording data for class '{args.label}' for {args.duration} seconds...")

        with open(csv_filename, mode="a", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)

            if write_header:
                csv_writer.writerow(["pc_timestamp", "esp32_timestamp_ms", "success_rate_pct", "avg_latency_us", "material_label"])

            start_time = time.time()
            recorded_samples = 0

            while (time.time() - start_time) < args.duration:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        try:
                            data = json.loads(line)

                            # Log to CSV with label
                            pc_timestamp = time.time()
                            csv_writer.writerow([
                                pc_timestamp,
                                data.get("timestamp_ms", ""),
                                data.get("success_rate_pct", ""),
                                data.get("avg_latency_us", ""),
                                args.label
                            ])
                            csvfile.flush()
                            recorded_samples += 1

                            # Print progress every 10 samples roughly
                            if recorded_samples % 10 == 0:
                                elapsed = time.time() - start_time
                                sys.stdout.write(f"\rRecorded {recorded_samples} samples... ({elapsed:.1f}/{args.duration}s)")
                                sys.stdout.flush()

                        except json.JSONDecodeError:
                            pass
                except serial.SerialException as e:
                    print(f"\nSerial read error: {e}")
                    break

            print(f"\nFinished recording. Total samples saved: {recorded_samples}")
            print(f"Data appended to {csv_filename}")

    except serial.SerialException as e:
        print(f"Could not open serial port {args.port}: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nRecording interrupted by user.")
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
