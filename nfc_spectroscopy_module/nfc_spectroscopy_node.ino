/**
 * Near-Field Impedance Spectroscopy Node
 *
 * This firmware implements a rapid-polling loop (100 Hz) to measure
 * the read success rate and response latency of a stationary NFC tag
 * using an ESP32 and RC522 module.
 *
 * Proxy Metric Logic:
 * Because the RC522 does not expose raw analog signals or RSSI values,
 * we measure the "Read Success Rate" (packet drop) and "Response Latency"
 * as proxy metrics. When a dielectric shift occurs between the reader
 * and tag, the inductive coupling degrades, increasing latency and
 * dropping reads.
 */

#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 22
#define SS_PIN  5

MFRC522 mfrc522(SS_PIN, RST_PIN);

unsigned long lastAttemptTime = 0;
const unsigned long attemptInterval = 10; // 10ms for 100 Hz
int attemptCount = 0;
int successCount = 0;
unsigned long totalLatencyUs = 0;
unsigned long lastReadTimeMs = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial);

  SPI.begin();
  mfrc522.PCD_Init();
  lastReadTimeMs = millis();
}

void resetRC522() {
  // Software watchdog reset sequence to prevent SPI bus hangs
  SPI.end();
  delay(10);
  SPI.begin();
  mfrc522.PCD_Init();
  lastReadTimeMs = millis();
}

void loop() {
  unsigned long currentTime = millis();

  // Software watchdog: re-initialize if no tag read for 5 seconds
  // This prevents hard crashes if the RC522 loses power or glitches.
  if (currentTime - lastReadTimeMs >= 5000) {
    resetRC522();
  }

  if (currentTime - lastAttemptTime >= attemptInterval) {
    lastAttemptTime = currentTime;

    unsigned long startUs = micros();
    bool success = false;

    // We use PICC_WakeupA to detect stationary tags that were halted,
    // or new tags in the field.
    byte bufferATQA[2];
    byte bufferSize = sizeof(bufferATQA);

    // Send WUPA (Wake-Up) command to the tag
    mfrc522.PICC_WakeupA(bufferATQA, &bufferSize);

    // Attempt to select and read the card's UID
    if (mfrc522.PICC_ReadCardSerial()) {
      success = true;
      // Halt the card so we can wake it up again in the next cycle
      mfrc522.PICC_HaltA();
    }

    unsigned long endUs = micros();

    attemptCount++;
    if (success) {
      successCount++;
      totalLatencyUs += (endUs - startUs);
      lastReadTimeMs = millis();
    }

    // Calculate and output metrics every 100 attempts (approx 1 second)
    if (attemptCount >= 100) {
      float success_rate_pct = (successCount / 100.0) * 100.0;
      unsigned long avg_latency_us = successCount > 0 ? (totalLatencyUs / successCount) : 0;

      // Strictly output the data over the Serial port as a minified JSON payload
      Serial.print("{\"timestamp_ms\": ");
      Serial.print(millis());
      Serial.print(", \"success_rate_pct\": ");
      Serial.print(success_rate_pct, 1);
      Serial.print(", \"avg_latency_us\": ");
      Serial.print(avg_latency_us);
      Serial.println("}");

      attemptCount = 0;
      successCount = 0;
      totalLatencyUs = 0;
    }
  }
}
