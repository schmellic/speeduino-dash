#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <Update.h>
#include "Telemetry.h"
#include "BridgeUpdate.h"

#ifndef SIMULATE
#define SIMULATE 1
#endif

#if CONFIG_IDF_TARGET_ESP32C3
#define SpeeduinoSerial Serial1   // C3 has no Serial2
constexpr int SPEEDUINO_RX = 4;
constexpr int SPEEDUINO_TX = 5;    // GPIO5, not GPIO21: GPIO21 is UART0 TX and the C3's boot text on it jammed the ECU's Serial3
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
// CRC-32 as the Speeduino uses it (the usual reflected one: zlib, Ethernet).
static uint32_t crc32(const uint8_t *p, size_t n) {
  uint32_t c = 0xFFFFFFFFu;
  while (n--) {
    c ^= *p++;
    for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
  }
  return ~c;
}

// Talks to the ECU's secondary serial in its "Tuner Studio" protocol (set the ECU's secondary serial protocol to "Tuner Studio").
// Unlike the plain "Generic" modes, every frame carries a length and a CRC and a half-received frame times out, so line noise
// (for example while this board reboots) just fails the CRC and is thrown away. In the Generic modes a stray byte such as 'M'
// or 'r' leaves the ECU waiting for parameter bytes with no timeout, and it stops answering until it is power-cycled.
//   request:  len(2, big-endian) | 'r', canId 0, 0x30, offset(2, LE), length(2, LE) | CRC32 of the payload (4, big-endian)
//   reply:    len(2) | rc (0 = OK), data | CRC32 of those bytes (4)
// Set when the ECU starts answering in plain-command style instead of framed (that is what it does once TunerStudio has
// connected over USB). From then on the bridge sends nothing, so it cannot collide with TunerStudio's traffic or feed the
// ECU more stray commands. Only a reboot of the bridge clears it: in the car the ignition cycle restarts the ECU and the
// bridge together.
static bool holdOff = false;

static bool readSpeeduino(Telemetry &t) {
  // Clear stale bytes, but never loop forever: a noisy or streaming RX line would otherwise freeze the bridge here.
  for (int i = 0; i < 256 && SpeeduinoSerial.available(); i++) SpeeduinoSerial.read();
  uint8_t req[2 + 7 + 4] = {0x00, 0x07, 'r', 0x00, 0x30, 0x00, 0x00, (uint8_t)REALTIME_LEN, 0x00};
  uint32_t rc = crc32(req + 2, 7);
  req[9] = rc >> 24; req[10] = rc >> 16; req[11] = rc >> 8; req[12] = rc;
  SpeeduinoSerial.write(req, sizeof(req));

  constexpr size_t REPLY_LEN = 2 + 1 + REALTIME_LEN + 4;
  uint8_t buf[REPLY_LEN];
  size_t n = 0;
  uint32_t start = millis();
  while (n < REPLY_LEN && millis() - start < 100) {
    if (SpeeduinoSerial.available()) buf[n++] = SpeeduinoSerial.read();
    else delay(1);   // don't spin flat out while the ECU is quiet: the C3 has one core and the radio needs its share
  }
#ifdef BRIDGE_DEBUG   // temporary: show the raw reply
  Serial.printf("raw n=%u:", (unsigned)n);
  for (size_t i = 0; i < n; i++) Serial.printf(" %02X", buf[i]);
  Serial.println();
#endif
  // A complete-looking reply that is not framed (no 00 21 header) is the ECU in plain-command mode: back off for good.
  if (n >= REALTIME_LEN && !(buf[0] == 0x00 && buf[1] == REALTIME_LEN + 1)) {
    holdOff = true;
    Serial.println("HOLD: the ECU answers in plain-command mode (TunerStudio connected?). Bridge stops polling until it is rebooted.");
    return false;
  }
  if (n != REPLY_LEN || buf[0] != 0x00 || buf[1] != REALTIME_LEN + 1 || buf[2] != 0x00) return false;
  uint32_t got = ((uint32_t)buf[REPLY_LEN - 4] << 24) | ((uint32_t)buf[REPLY_LEN - 3] << 16) | ((uint32_t)buf[REPLY_LEN - 2] << 8) | buf[REPLY_LEN - 1];
  if (got != crc32(buf + 2, REALTIME_LEN + 1)) return false;
  const uint8_t *d = buf + 3;

  t.mapKpa     = d[4] | (d[5] << 8);
  t.iatC       = (int16_t)d[6] - 40;
  t.cltC       = (int16_t)d[7] - 40;
  t.battMv     = d[9] * 100;
  t.o2Raw      = d[10];
  t.afrTarget  = d[21];
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
  t.afrTarget  = 147;
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
  Serial.setTxTimeoutMs(0);   // never wait for a USB reader: with the cable plugged in but nothing reading, every printf used to stall the loop for seconds and the dash got about one packet every two seconds
#if !SIMULATE
  SpeeduinoSerial.begin(SPEEDUINO_BAUD, SERIAL_8N1, SPEEDUINO_RX, SPEEDUINO_TX);
#endif
#ifdef BRIDGE_PROBE   // temporary: show how the ECU answers a framed request and a plain one
  delay(3000);
  for (;;) {
    for (int mode = 0; mode < 3; mode++) {
      while (SpeeduinoSerial.available()) SpeeduinoSerial.read();
      uint8_t f[16];
      size_t fn = 0;
      if (mode == 0) {   // framed 'Q'
        f[0] = 0; f[1] = 1; f[2] = 'Q';
        uint32_t c = crc32(f + 2, 1);
        f[3] = c >> 24; f[4] = c >> 16; f[5] = c >> 8; f[6] = c; fn = 7;
      } else if (mode == 1) { f[0] = 'Q'; fn = 1; }   // plain 'Q'
      else { f[0] = 'S'; fn = 1; }                    // plain 'S'
      SpeeduinoSerial.write(f, fn);
      uint8_t rb[64];
      size_t rn = 0;
      uint32_t t0 = millis();
      while (rn < sizeof(rb) && millis() - t0 < 300) { if (SpeeduinoSerial.available()) rb[rn++] = SpeeduinoSerial.read(); else delay(1); }
      Serial.printf("probe %s n=%u:", mode == 0 ? "framed-Q" : mode == 1 ? "plain-Q" : "plain-S", (unsigned)rn);
      for (size_t i = 0; i < rn; i++) Serial.printf(" %02X", rb[i]);
      Serial.print("  |");
      for (size_t i = 0; i < rn; i++) Serial.print(rb[i] >= 32 && rb[i] < 127 ? (char)rb[i] : '.');
      Serial.println();
      delay(500);
    }
    Serial.println("---");
  }
#endif
#ifdef BRIDGE_BAUDSCAN   // temporary: try single-byte commands at two baud rates, show what the ECU sends back
  delay(3000);
  const uint32_t bauds[] = {115200, 9600};
  const char cmds[] = {'Q', 'S', 'n', 'N', 'A', 'r'};
  for (;;) {
    for (uint32_t b : bauds) {
      SpeeduinoSerial.updateBaudRate(b);
      delay(50);
      for (char c : cmds) {
        while (SpeeduinoSerial.available()) SpeeduinoSerial.read();
        if (c == 'r') { const uint8_t r[] = {'r', 0x00, 0x30, 0x00, 0x00, 0x20, 0x00}; SpeeduinoSerial.write(r, sizeof(r)); }
        else SpeeduinoSerial.write((uint8_t)c);
        uint8_t rb[40];
        size_t rn = 0;
        uint32_t t0 = millis();
        while (rn < sizeof(rb) && millis() - t0 < 300) { if (SpeeduinoSerial.available()) rb[rn++] = SpeeduinoSerial.read(); else delay(1); }
        Serial.printf("baud %u cmd %c n=%u:", (unsigned)b, c, (unsigned)rn);
        for (size_t i = 0; i < rn && i < 20; i++) Serial.printf(" %02X", rb[i]);
        Serial.print("  |");
        for (size_t i = 0; i < rn && i < 20; i++) Serial.print(rb[i] >= 32 && rb[i] < 127 ? (char)rb[i] : '.');
        Serial.println();
        delay(150);
      }
    }
    Serial.println("---");
  }
#endif
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(RADIO_CHANNEL, WIFI_SECOND_CHAN_NONE);   // same channel as the dash's access point
#ifdef BRIDGE_RADIOSCAN   // temporary: can this board's radio hear the dash's access point, and how loud?
  delay(1500);
  for (int round = 0; round < 3; round++) {
    int found = WiFi.scanNetworks();
    Serial.printf("scan %d: %d networks\n", round, found);
    for (int i = 0; i < found; i++) {
      if (WiFi.SSID(i) == "SpeeduinoDash") Serial.printf("  SpeeduinoDash heard: rssi %d dBm, channel %d\n", (int)WiFi.RSSI(i), (int)WiFi.channel(i));
    }
  }
  WiFi.scanDelete();
#endif
  // The C3 SuperMini's radio is not heard by the dash at full transmit power (its small 3.3 V regulator sags under the transmit
  // peaks and the signal is mangled): with the default 20 dBm the dash received nothing, at 8.5 dBm it receives every packet.
  // The dash is only a couple of metres away, so low power is plenty. Verified on the bench 2026-11-27.
#ifndef BRIDGE_TX_POWER
#define BRIDGE_TX_POWER WIFI_POWER_8_5dBm
#endif
  WiFi.setTxPower(BRIDGE_TX_POWER);
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
#ifdef BRIDGE_DEBUG
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_now_register_send_cb([](const esp_now_send_info_t *, esp_now_send_status_t st) { Serial.printf("send status %d (0 = ok)\n", (int)st); });
#else
  esp_now_register_send_cb([](const uint8_t *, esp_now_send_status_t st) { Serial.printf("send status %d (0 = ok)\n", (int)st); });
#endif
#endif
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
  t.linkOk = (!holdOff && readSpeeduino(t)) ? 1 : 0;
#endif
  engineRpm = t.rpm;
  engineLink = t.linkOk;
  t.seq = seq++;
  esp_err_t sendRc = esp_now_send(BROADCAST, (uint8_t *)&t, sizeof(t));
#ifdef BRIDGE_DEBUG
  Serial.printf("esp_now_send rc=%d (0 = queued) ch=%u\n", (int)sendRc, (unsigned)WiFi.channel());
#else
  (void)sendRc;
#endif
  Serial.printf("rpm=%u map=%u clt=%d link=%u\n", t.rpm, t.mapKpa, t.cltC, t.linkOk);
}
