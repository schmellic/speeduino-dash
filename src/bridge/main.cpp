#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <Update.h>
#include "Telemetry.h"
#include "BridgeUpdate.h"

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
constexpr size_t REALTIME_LEN = 32;   // only the first 32 bytes of the realtime block are needed
constexpr uint32_t POLL_MS = 50;      // 20 Hz

static const uint8_t BROADCAST[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
static uint8_t seq = 0;

// Offsets taken from [OutputChannels] in the 61Bug mainController.ini (speeduino 202402).
// Request is the ini's ochGetCommand: 'r', canId, 0x30, offset (2 bytes), length (2 bytes).
static bool readSpeeduino(Telemetry &t) {
  while (SpeeduinoSerial.available()) SpeeduinoSerial.read();
  const uint8_t req[] = {'r', 0x00, 0x30, 0x00, 0x00, (uint8_t)REALTIME_LEN, 0x00};
  SpeeduinoSerial.write(req, sizeof(req));

  uint8_t buf[REALTIME_LEN + 1];
  size_t n = 0;
  uint32_t start = millis();
  while (n < REALTIME_LEN + 1 && millis() - start < 100) {
    if (SpeeduinoSerial.available()) buf[n++] = SpeeduinoSerial.read();
  }
  // Some firmware echoes 'r' before the data; skip it if the length says so.
  const uint8_t *d = buf;
  if (n == REALTIME_LEN + 1 && buf[0] == 'r') d = buf + 1;
  else if (n < REALTIME_LEN) return false;

  t.mapKpa     = d[4] | (d[5] << 8);
  t.iatC       = (int16_t)d[6] - 40;
  t.cltC       = (int16_t)d[7] - 40;
  t.battMv     = d[9] * 100;
  t.o2Raw      = d[10];
  t.rpm        = d[14] | (d[15] << 8);
  t.advanceDeg = (int8_t)d[24];
  t.tpsPct     = d[25] / 2;
  return true;
}

static void simulate(Telemetry &t) {
  float s = millis() / 1000.0f;
  t.rpm        = 3000 + 2900 * sinf(s * 0.6f);   // 100-5900: green, orange and red on the dash
  t.mapKpa     = 60 + 40 * sinf(s * 0.6f + 0.5f);
  t.cltC       = 88 + 4 * sinf(s * 0.05f);
  t.iatC       = 32;
  t.battMv     = 13800;
  t.tpsPct     = 25 + 25 * sinf(s * 0.6f + 0.5f);
  t.advanceDeg = 20 + 8 * sinf(s * 0.6f);
  t.o2Raw      = 147;
}

static uint16_t engineRpm = 0;
static bool engineLink = false;

#if BRIDGE_UPDATE
// ---- Firmware update over ESP-NOW (protocol in include/BridgeUpdate.h) ------------------------------------------
// The receive callback only queues the packet; flash writes happen in loop().
static uint8_t rxBuf[250], rxMac[6];
static volatile int rxLen = 0;
static volatile bool rxPending = false;
static bool updating = false, haveNonce = false;
static uint8_t nonce[upd::NONCE_LEN];
static uint32_t expectOff = 0, lastUpdMs = 0;
static upd::Sha sha;

static void queueRx(const uint8_t *mac, const uint8_t *d, int n) {
  if (rxPending || n < 2 || n > (int)sizeof(rxBuf) || d[0] != upd::MAGIC) return;
  memcpy(rxBuf, d, n);
  memcpy(rxMac, mac, 6);
  rxLen = n;
  rxPending = true;
}
#if ESP_ARDUINO_VERSION_MAJOR >= 3
static void onRecv(const esp_now_recv_info_t *i, const uint8_t *d, int n) { queueRx(i->src_addr, d, n); }
#else
static void onRecv(const uint8_t *mac, const uint8_t *d, int n) { queueRx(mac, d, n); }
#endif

static void reply(const uint8_t *mac, const uint8_t *msg, size_t n) {
  if (!esp_now_is_peer_exist(mac)) {
    esp_now_peer_info_t p = {};
    memcpy(p.peer_addr, mac, 6);
    p.channel = 0;
    p.encrypt = false;
    esp_now_add_peer(&p);
  }
  esp_now_send(mac, msg, n);
}
static void ack(const uint8_t *mac, uint8_t status, uint32_t next) {
  uint8_t m[7] = {upd::MAGIC, upd::ACK, status};
  memcpy(m + 3, &next, 4);
  reply(mac, m, sizeof(m));
}
static void abortUpdate() {
  if (updating) Update.abort();
  sha.stop();
  updating = false;
  haveNonce = false;
}

static void updatePoll() {
  if (updating && millis() - lastUpdMs > 5000) abortUpdate();   // dash went quiet: go back to broadcasting
  if (!rxPending) return;
  uint8_t m[250], mac[6];
  int n = rxLen;
  memcpy(m, rxBuf, n);
  memcpy(mac, rxMac, 6);
  rxPending = false;
  lastUpdMs = millis();

  switch (m[1]) {
    case upd::HELLO: {
      if (!SIMULATE && engineLink && engineRpm > 300) { ack(mac, upd::REFUSED, 0); break; }   // never while the engine runs
      abortUpdate();
      esp_fill_random(nonce, sizeof(nonce));
      haveNonce = true;
      uint8_t r[2 + upd::NONCE_LEN] = {upd::MAGIC, upd::NONCE};
      memcpy(r + 2, nonce, sizeof(nonce));
      reply(mac, r, sizeof(r));
      break;
    }
    case upd::BEGIN: {
      if (updating) { ack(mac, upd::OK, expectOff); break; }   // retry of a BEGIN whose ack was lost
      uint8_t want[upd::MAC_LEN];
      if (n != 2 + (int)upd::MAC_LEN || !haveNonce) { ack(mac, upd::BAD_AUTH, 0); break; }
      upd::beginMac(nonce, want);
      if (!upd::macEq(want, m + 2)) { haveNonce = false; ack(mac, upd::BAD_AUTH, 0); break; }
      if (!Update.begin(UPDATE_SIZE_UNKNOWN)) { ack(mac, upd::BEGIN_FAIL, 0); break; }
      updating = true;
      expectOff = 0;
      sha.start();
      ack(mac, upd::OK, 0);
      break;
    }
    case upd::DATA: {
      if (!updating) { ack(mac, upd::NOT_STARTED, 0); break; }
      if (n < 6) break;
      uint32_t off;
      memcpy(&off, m + 2, 4);
      size_t len = n - 6;
      if (off == expectOff && len > 0) {
        if (Update.write(m + 6, len) != len) { abortUpdate(); ack(mac, upd::WRITE_FAIL, 0); break; }
        sha.add(m + 6, len);
        expectOff += len;
      }
      ack(mac, upd::OK, expectOff);   // a duplicate or a gap just gets the offset we are waiting for
      break;
    }
    case upd::END: {
      if (!updating) { ack(mac, upd::NOT_STARTED, 0); break; }
      if (n != 6 + (int)upd::MAC_LEN) break;
      uint32_t size;
      memcpy(&size, m + 2, 4);
      uint8_t hash[32], want[upd::MAC_LEN];
      sha.finish(hash);
      upd::endMac(nonce, size, hash, want);
      if (size != expectOff || !upd::macEq(want, m + 6)) { abortUpdate(); ack(mac, upd::BAD_HASH, 0); break; }
      if (!Update.end(true)) { abortUpdate(); ack(mac, upd::WRITE_FAIL, 0); break; }
      ack(mac, upd::OK, size);
      delay(300);   // let the ack leave before restarting into the new image
      ESP.restart();
      break;
    }
    case upd::ABORT:
      abortUpdate();
      break;
  }
}
#endif

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
#if BRIDGE_UPDATE
  esp_now_register_recv_cb(onRecv);
#endif
}

void loop() {
#if BRIDGE_UPDATE
  updatePoll();
  if (updating) return;   // no polling or broadcasting while the image is arriving
#endif
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
  engineRpm = t.rpm;
  engineLink = t.linkOk;
  t.seq = seq++;
  esp_now_send(BROADCAST, (uint8_t *)&t, sizeof(t));
  Serial.printf("rpm=%u map=%u clt=%d link=%u\n", t.rpm, t.mapKpa, t.cltC, t.linkOk);
}
