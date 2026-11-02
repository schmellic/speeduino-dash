#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include "Telemetry.h"

constexpr uint32_t STALE_MS = 500;   // no packet for this long = link lost

static volatile Telemetry latest = {};
static volatile uint32_t lastRxMs = 0;

static void handlePacket(const uint8_t *data, int len) {
  if (len != sizeof(Telemetry)) return;
  memcpy((void *)&latest, data, sizeof(Telemetry));
  lastRxMs = millis();
}

#if ESP_ARDUINO_VERSION_MAJOR >= 3
static void onRecv(const esp_now_recv_info_t *, const uint8_t *data, int len) {
  handlePacket(data, len);
}
#else
static void onRecv(const uint8_t *, const uint8_t *data, int len) {
  handlePacket(data, len);
}
#endif

static bool linkAlive() {
  return millis() - lastRxMs < STALE_MS && latest.linkOk;
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  esp_now_register_recv_cb(onRecv);
}

void loop() {
  static uint32_t last = 0;
  if (millis() - last < 200) return;
  last = millis();

  Telemetry t;
  memcpy(&t, (const void *)&latest, sizeof(t));
  if (linkAlive())
    Serial.printf("rpm=%u map=%u clt=%d iat=%d batt=%umV\n", t.rpm, t.mapKpa, t.cltC, t.iatC, t.battMv);
  else
    Serial.println("no data");
}
