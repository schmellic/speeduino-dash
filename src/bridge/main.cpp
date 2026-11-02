#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include "Telemetry.h"

#ifndef SIMULATE
#define SIMULATE 1
#endif

#if CONFIG_IDF_TARGET_ESP32C3
#define SpeeduinoSerial Serial1   // C3 has no Serial2
constexpr int SPEEDUINO_RX = 4;
constexpr int SPEEDUINO_TX = 5;
#else
#define SpeeduinoSerial Serial2
constexpr int SPEEDUINO_RX = 16;
constexpr int SPEEDUINO_TX = 17;
#endif
constexpr uint32_t SPEEDUINO_BAUD = 115200;
constexpr size_t REALTIME_LEN = 75;   // 'A' command reply length; verify against your firmware's .ini
constexpr uint32_t POLL_MS = 50;      // 20 Hz

static const uint8_t BROADCAST[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
static uint8_t seq = 0;

// Offsets within the realtime block. Check against [OutputChannels] in your speeduino.ini.
static bool readSpeeduino(Telemetry &t) {
  while (SpeeduinoSerial.available()) SpeeduinoSerial.read();
  SpeeduinoSerial.write('A');

  uint8_t buf[REALTIME_LEN];
  size_t n = 0;
  uint32_t start = millis();
  while (n < REALTIME_LEN && millis() - start < 100) {
    if (SpeeduinoSerial.available()) buf[n++] = SpeeduinoSerial.read();
  }
  if (n < REALTIME_LEN) return false;

  t.mapKpa     = buf[4] | (buf[5] << 8);
  t.iatC       = (int16_t)buf[6] - 40;
  t.cltC       = (int16_t)buf[7] - 40;
  t.battMv     = buf[9] * 100;
  t.o2Raw      = buf[10];
  t.rpm        = buf[14] | (buf[15] << 8);
  t.advanceDeg = (int8_t)buf[23];
  t.tpsPct     = buf[24] / 2;
  return true;
}

static void simulate(Telemetry &t) {
  float s = millis() / 1000.0f;
  t.rpm        = 2500 + 2200 * sinf(s * 0.6f);
  t.mapKpa     = 60 + 40 * sinf(s * 0.6f + 0.5f);
  t.cltC       = 88 + 4 * sinf(s * 0.05f);
  t.iatC       = 32;
  t.battMv     = 13800;
  t.tpsPct     = 25 + 25 * sinf(s * 0.6f + 0.5f);
  t.advanceDeg = 20 + 8 * sinf(s * 0.6f);
  t.o2Raw      = 147;
}

void setup() {
  Serial.begin(115200);
#if !SIMULATE
  SpeeduinoSerial.begin(SPEEDUINO_BAUD, SERIAL_8N1, SPEEDUINO_RX, SPEEDUINO_TX);
#endif
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, BROADCAST, 6);
  peer.channel = 0;
  peer.encrypt = false;
  esp_now_add_peer(&peer);
}

void loop() {
  static uint32_t last = 0;
  if (millis() - last < POLL_MS) return;
  last = millis();

  Telemetry t = {};
#if SIMULATE
  simulate(t);
  t.linkOk = 1;
#else
  t.linkOk = readSpeeduino(t) ? 1 : 0;
#endif
  t.seq = seq++;
  esp_now_send(BROADCAST, (uint8_t *)&t, sizeof(t));
  Serial.printf("rpm=%u map=%u clt=%d link=%u\n", t.rpm, t.mapKpa, t.cltC, t.linkOk);
}
