import serial
import json
import csv
import time
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="NFC Serial Analyzer Data Acquisition Server")
    parser.add_argument("port", help="The serial port to connect to (e.g., /dev/ttyUSB0 or COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    args = parser.parse_args()

    csv_filename = "impedance_dataset.csv"

    # Check if we need to write the header
    write_header = False
    try:
        with open(csv_filename, "r") as f:
            if not f.read(1):
                write_header = True
    except FileNotFoundError:
        write_header = True

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
        print(f"Connected to {args.port} at {args.baud} baud.")

        with open(csv_filename, mode="a", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)

            if write_header:
                csv_writer.writerow(["pc_timestamp", "esp32_timestamp_ms", "success_rate_pct", "avg_latency_us"])

            while True:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        try:
                            data = json.loads(line)

                            # Log to CSV
                            pc_timestamp = time.time()
                            csv_writer.writerow([
                                pc_timestamp,
                                data.get("timestamp_ms", ""),
                                data.get("success_rate_pct", ""),
                                data.get("avg_latency_us", "")
                            ])
                            csvfile.flush() # Ensure data is written
                            print(f"Logged: {data}")
                        except json.JSONDecodeError:
                            print(f"Failed to parse JSON: {line}")
                except serial.SerialException as e:
                    print(f"Serial read error: {e}")
                    break
    except serial.SerialException as e:
        print(f"Could not open serial port {args.port}: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
