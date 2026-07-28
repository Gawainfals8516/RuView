# Near-Field Impedance Spectroscopy Module

This module implements a hardware-in-the-loop workaround for Near-Field Impedance Spectroscopy using an ESP32 and a standard RC522 RFID/NFC module (13.56 MHz).

## Hardware Definition & Pinout

Since the standard RC522 module communicates via SPI and does not expose raw analog signals or native impedance/RSSI values, we use proxy metrics. The ESP32 measures the "Read Success Rate" (packet drop) and "Response Latency" to detect antenna detuning caused by dielectric shifts.

To replicate the setup, connect the ESP32 to the RC522 using the standard VSPI pins as follows:

| RC522 Pin | ESP32 Pin |
|-----------|-----------|
| SDA (SS)  | GPIO 5    |
| SCK       | GPIO 18   |
| MOSI      | GPIO 23   |
| MISO      | GPIO 19   |
| RST       | GPIO 22   |
| 3.3V      | 3.3V      |
| GND       | GND       |

## Python Dependencies

The Data Acquisition Server requires Python 3 and the `pyserial` dependency.

To install the necessary dependencies, run:

```bash
pip install pyserial
```

## Running the Data Acquisition Server

To start logging data, connect the ESP32 to your PC and run the script with your serial port as an argument:

```bash
python nfc_serial_analyzer.py /dev/ttyUSB0
```
(Replace `/dev/ttyUSB0` with the appropriate COM port for your system, e.g., `COM3` on Windows).

### Real-Time Dashboard Dependencies

If you wish to use the graphical real-time dashboard with the state machine (`dashboard_nfc.py`), you must install `matplotlib`:

```bash
pip install matplotlib
```
