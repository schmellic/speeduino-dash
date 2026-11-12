#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <ArduinoOTA.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Update.h>
#include <Arduino_GFX_Library.h>
#include <Arduino_GC9B72.h>
#include "Telemetry.h"

#ifndef SIM_LOCAL
#define SIM_LOCAL 0
#endif
#ifndef INFO_SCREEN
#define INFO_SCREEN 1   // 0 = leave the info screen alone (not connected)
#endif

// ---- Wiring (classic ESP32) -------------------------------------------
constexpr int PIN_SCK = 18, PIN_MOSI = 23, PIN_DC = 21;
constexpr int PIN_TACH_CS = 5,  PIN_TACH_RST = 22, PIN_TACH_BL = 25;
constexpr int PIN_INFO_CS = 4,  PIN_INFO_RST = 27, PIN_INFO_BL = 26;

// ---- Gauge settings ----------------------------------------------------
constexpr int RPM_MAX = 6000;
constexpr int RPM_SHIFT = 4500;     // ring turns orange here (user)
constexpr int RPM_REDLINE = 5400;   // Beetle redline (user): digits and ring turn red here
constexpr int HEAD_WARN_C = 190, HEAD_DANGER_C = 220;
constexpr uint32_t STALE_MS = 500;

// ---- OTA ---------------------------------------------------------------
// No network in the car, so for the first OTA_WINDOW_MS after power-on the dash runs its own access point. Join it from the
// laptop and run `pio run -e dash_ota -t upload`. The AP then shuts off so it can't get in the way of ESP-NOW.
constexpr uint32_t OTA_WINDOW_MS = 120000;
constexpr const char *OTA_SSID = "SpeeduinoDash";
// Wi-Fi password only; the upload page and PlatformIO upload need no login. Kept out of the repo: put your own in
// src/dash/secrets.h (git-ignored, see secrets.example.h). Without that file the build falls back to a placeholder.
#if __has_include("secrets.h")
#include "secrets.h"
#else
#define OTA_PASS "change-me-123"
#endif
static bool otaActive = false, otaBusy = false;

// Browser upload at http://192.168.4.1 : pick .pio/build/dash/firmware.bin and press Update.
static WebServer web(80);
static DNSServer dns;   // answers every name with the dash, so phones treat the network as a captive portal
static const char UPLOAD_PAGE[] PROGMEM = R"HTML(<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<body style="font-family:sans-serif;background:#111;color:#eee;max-width:420px;margin:2em auto;padding:0 1em">
<h2>Speeduino dash update</h2>
<input type=file id=f><br><br>
<button onclick="go()" style="padding:.6em 1.2em">Update</button>
<p id=s></p>
<p style="color:#999;font-size:.85em">If Choose file does nothing, close this sign-in window and open http://192.168.4.1 in Chrome or Safari.</p>
<script>
function go(){var f=document.getElementById('f').files[0],s=document.getElementById('s');
if(!f){s.textContent='Choose a .bin file first';return}
var x=new XMLHttpRequest(),d=new FormData();d.append('fw',f);
x.upload.onprogress=function(e){s.textContent='Uploading '+Math.round(e.loaded*100/e.total)+'%'};
x.onload=function(){s.textContent=x.responseText};
x.onerror=function(){s.textContent='Upload failed'};
x.open('POST','/update');x.send(d)}
</script>)HTML";

static void webSetup() {
  web.on("/", HTTP_GET, []() {
    web.send_P(200, "text/html", UPLOAD_PAGE);
  });
  web.on("/update", HTTP_POST, []() {
    bool ok = !Update.hasError();
    web.send(200, "text/plain", ok ? "Update done, restarting the dash." : "Update failed. Try again.");
    if (ok) { delay(500); ESP.restart(); }
  }, []() {
    HTTPUpload &u = web.upload();
    if (u.status == UPLOAD_FILE_START) { otaBusy = true; Update.begin(UPDATE_SIZE_UNKNOWN); }
    else if (u.status == UPLOAD_FILE_WRITE) Update.write(u.buf, u.currentSize);
    else if (u.status == UPLOAD_FILE_END) { Update.end(true); otaBusy = false; }
    else if (u.status == UPLOAD_FILE_ABORTED) { Update.abort(); otaBusy = false; }
  });
  web.onNotFound([]() {   // connectivity checks and any other address land on the upload page
    web.sendHeader("Location", "http://192.168.4.1/", true);
    web.send(302, "text/plain", "");
  });
  web.begin();
  dns.start(53, "*", WiFi.softAPIP());
}

// ---- Displays (both share SCK/MOSI/DC, each has its own CS and RST) ----
Arduino_DataBus *busTach = new Arduino_ESP32SPI(PIN_DC, PIN_TACH_CS, PIN_SCK, PIN_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *tach = new Arduino_GC9B72(busTach, PIN_TACH_RST, 0, false, 360, 360);
Arduino_DataBus *busInfo = new Arduino_ESP32SPI(PIN_DC, PIN_INFO_CS, PIN_SCK, PIN_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *info = new Arduino_ILI9341(busInfo, PIN_INFO_RST, 1, true);   // landscape 320x240

constexpr uint16_t C_BG = RGB565_BLACK, C_FG = RGB565_WHITE, C_DIM = RGB565_DARKGREY;
constexpr uint16_t C_WARN = RGB565_ORANGE, C_BAD = RGB565_RED, C_OK = RGB565_GREEN;

// ---- Telemetry in ------------------------------------------------------
static volatile Telemetry latest = {};
static volatile uint32_t lastRxMs = 0;

static void handlePacket(const uint8_t *data, int len) {
  if (len != sizeof(Telemetry)) return;
  memcpy((void *)&latest, data, sizeof(Telemetry));
  lastRxMs = millis();
}
#if ESP_ARDUINO_VERSION_MAJOR >= 3
static void onRecv(const esp_now_recv_info_t *, const uint8_t *d, int n) { handlePacket(d, n); }
#else
static void onRecv(const uint8_t *, const uint8_t *d, int n) { handlePacket(d, n); }
#endif

static bool getTelemetry(Telemetry &t) {
#if SIM_LOCAL
  float s = millis() / 1000.0f;
  t = {};
  t.rpm = 2800 + 2700 * sinf(s * 0.5f);
  t.mapKpa = 60 + 40 * sinf(s * 0.5f + 0.5f);
  t.cltC = 150 + 50 * sinf(s * 0.05f);
  t.iatC = 32;
  t.battMv = 13800 + 600 * sinf(s * 0.2f);
  t.tpsPct = 25 + 25 * sinf(s * 0.5f + 0.5f);
  t.advanceDeg = 20 + 8 * sinf(s * 0.5f);
  t.o2Raw = 147;
  t.linkOk = 1;
  return true;
#else
  memcpy(&t, (const void *)&latest, sizeof(t));
  return millis() - lastRxMs < STALE_MS && t.linkOk;
#endif
}

// ---- Tach: numerals on a dark ring that lights green / orange / red ------------------------------------------------------
// No needle and no frame buffer: the ring is 60 blocks of 100 rpm that are lit or cleared as the revs change, so nothing
// is ever erased by a thin shape. Only the blocks that change are redrawn, then the numerals go back on top.
constexpr int CX = 180, CY = 180;
constexpr int SEG_RPM = 100, SEG_N = RPM_MAX / SEG_RPM;   // 60 blocks; 100 divides the 5400 redline
constexpr int RING_IN = 116, RING_OUT = 166;              // lit blocks (50 px thick)
constexpr int BAND_IN = 114, BAND_OUT = 168;              // dark ring behind them
constexpr uint16_t C_RIM = 0xBDF7, C_BAND = 0x18E3, C_DISC = 0x8C71;
constexpr uint16_t C_GREEN = 0x4D63, C_ORANGE = 0xF440, C_RED = 0xE0E5, C_REDDIM = 0x5862;

static float rpmToDeg(float rpm) {
  return 135.0f + constrain(rpm, 0, RPM_MAX) * 270.0f / RPM_MAX;
}
static void polarF(float deg, float r, float &x, float &y) {
  float a = deg * DEG_TO_RAD;
  x = CX + r * cosf(a);
  y = CY + r * sinf(a);
}

// Fill a convex quad one scanline at a time. The library's fillTriangle left stray pixels beyond thin tips, so all
// shapes that get redrawn use this instead.
static void fillQuad(const float (&x)[4], const float (&y)[4], uint16_t c) {
  float ymin = min(min(y[0], y[1]), min(y[2], y[3]));
  float ymax = max(max(y[0], y[1]), max(y[2], y[3]));
  for (int row = (int)ceilf(ymin); row <= (int)floorf(ymax); row++) {
    float lo = 1e9f, hi = -1e9f;
    for (int i = 0; i < 4; i++) {
      int j = (i + 1) & 3;
      if (row < min(y[i], y[j]) || row > max(y[i], y[j])) continue;
      if (y[i] == y[j]) {
        lo = min(lo, min(x[i], x[j]));
        hi = max(hi, max(x[i], x[j]));
      } else {
        float xx = x[i] + (row - y[i]) * (x[j] - x[i]) / (y[j] - y[i]);
        lo = min(lo, xx);
        hi = max(hi, xx);
      }
    }
    if (hi >= lo) {
      int xl = lroundf(lo), xr = lroundf(hi);
      tach->drawFastHLine(xl, row, xr - xl + 1, c);
    }
  }
}

static void fillSector(float a0, float a1, float rIn, float rOut, uint16_t c) {
  float x0, y0, x1, y1, x2, y2, x3, y3;
  polarF(a0, rOut, x0, y0);
  polarF(a1, rOut, x1, y1);
  polarF(a1, rIn, x2, y2);
  polarF(a0, rIn, x3, y3);
  float qx[4] = {x0, x1, x2, x3}, qy[4] = {y0, y1, y2, y3};
  fillQuad(qx, qy, c);
}

static void drawSegment(int i, uint16_t c) {
  fillSector(rpmToDeg(i * SEG_RPM) + 0.25f, rpmToDeg((i + 1) * SEG_RPM) - 0.25f, RING_IN, RING_OUT, c);
}
static uint16_t segLit(int i) {
  int r = i * SEG_RPM;
  return r >= RPM_REDLINE ? C_RED : r >= RPM_SHIFT ? C_ORANGE : C_GREEN;
}

// Centre a string on (cx, cy) using the current font's bounds.
static void textCentered(const char *s, int cx, int cy) {
  int16_t x1, y1;
  uint16_t w, h;
  tach->getTextBounds(s, 0, 0, &x1, &y1, &w, &h);
  tach->setCursor(cx - (x1 + w / 2), cy - (y1 + h / 2));
  tach->print(s);
}

static void drawNumerals() {
  tach->setFont(u8g2_font_helvB24_tn);
  tach->setTextColor(C_FG);
  char b[2] = {0, 0};
  for (int k = 0; k <= RPM_MAX / 1000; k++) {
    float x, y;
    polarF(rpmToDeg(k * 1000), (RING_IN + RING_OUT) / 2.0f, x, y);
    b[0] = '0' + k;
    textCentered(b, lroundf(x), lroundf(y));
  }
}

static void drawTachFace() {
  tach->fillScreen(C_BG);
  tach->setUTF8Print(true);
  tach->drawCircle(CX, CY, 178, C_RIM);
  tach->drawCircle(CX, CY, 177, C_RIM);
  tach->fillCircle(CX, CY, BAND_OUT, C_BAND);
  tach->fillCircle(CX, CY, BAND_IN, C_BG);
  for (int i = RPM_REDLINE / SEG_RPM; i < SEG_N; i++) drawSegment(i, C_REDDIM);
  for (int r = 0; r <= RPM_MAX; r += 250) {   // fine ticks outside the ring, never redrawn
    float a = rpmToDeg(r);
    bool major = r % 1000 == 0;
    fillSector(a - (major ? 0.5f : 0.25f), a + (major ? 0.5f : 0.25f), major ? 170 : 172, 176, C_FG);
  }
  tach->drawCircle(CX, CY, 104, C_DISC);   // centre outline, 2 px, 10 px inside the ring
  tach->drawCircle(CX, CY, 105, C_DISC);
  drawNumerals();
  tach->setFont(u8g2_font_helvB10_tr);
  tach->setTextColor(C_DIM);
  textCentered("RPM", CX, CY - 52);
}

static void drawDigits(int rpm) {
  char buf[8];
  snprintf(buf, sizeof(buf), "%d", rpm);
  tach->fillRect(CX - 86, CY - 28, 172, 72, C_BG);
  tach->setFont(u8g2_font_logisoso58_tn);
  tach->setTextColor(rpm >= RPM_REDLINE ? C_RED : C_FG);
  textCentered(buf, CX, CY + 8);
}
static void drawNoData() {
  tach->fillRect(CX - 86, CY - 28, 172, 72, C_BG);
  tach->fillRect(CX - 40, CY + 4, 80, 8, C_DIM);   // a dim bar instead of digits
}

static float shownRpm = 0;
static int litSegs = 0;
static int lastDigits = -1;
static bool tachShowsNoData = true;

// Wider than a block, so no stray edge pixel of a cleared block can survive in the gaps.
static void clearSegment(int i) {
  fillSector(rpmToDeg(i * SEG_RPM) - 0.4f, rpmToDeg((i + 1) * SEG_RPM) + 0.4f, RING_IN - 1, RING_OUT + 1, C_BAND);
}

// Clear every block whose state changed plus its neighbours, then redraw them (and one more block each side, which the
// clearing spills onto) in their final colours, then put the numerals back on top.
static void setLitSegments(int want) {
  int lo = min(want, litSegs), hi = max(want, litSegs);
  for (int i = max(lo - 1, 0); i <= min(hi, SEG_N - 1); i++) clearSegment(i);
  for (int i = max(lo - 2, 0); i <= min(hi + 1, SEG_N - 1); i++) {
    if (i < want) drawSegment(i, segLit(i));
    else if (i * SEG_RPM >= RPM_REDLINE) drawSegment(i, C_REDDIM);
  }
  litSegs = want;
  drawNumerals();
}

static void updateTach(const Telemetry &t, bool alive) {
  if (!alive) {
    if (!tachShowsNoData) {
      setLitSegments(0);
      drawNoData();
      tachShowsNoData = true;
      lastDigits = -1;
    }
    return;
  }
  tachShowsNoData = false;
  shownRpm += (t.rpm - shownRpm) * 0.35f;
  int want = constrain((int)((shownRpm + SEG_RPM / 2) / SEG_RPM), 0, SEG_N);
  if (want != litSegs) setLitSegments(want);
  int digits = (int)(shownRpm / 10) * 10;
  if (digits != lastDigits) {
    lastDigits = digits;
    drawDigits(digits);
  }
}

// ---- Info screen (same look as the tach: black ground, dark panels, rim-grey labels, green/orange/red status) ----------
// 2 columns x 4 rows of rounded panels. Each has a status stripe down the left edge, a small label, and a value with a
// small unit after it. The throttle panel also has a bar.
constexpr int PANEL_W = 148, PANEL_H = 50, PANEL_GAP = 6, PANEL_X0 = 8, PANEL_Y0 = 11, CELLS = 8;
struct Cell { const char *label; char last[8]; char lastUnit[4]; uint16_t lastColor, lastStripe; int lastBar; };
static Cell cells[CELLS] = {
  {"HEAD TEMP"}, {"PEAK HEAD"}, {"THROTTLE"}, {"MAP"}, {"AFR"}, {"ADVANCE"}, {"INTAKE"}, {"BATTERY"},
};

static int panelX(int i) { return PANEL_X0 + (i % 2) * (PANEL_W + PANEL_GAP + 2); }
static int panelY(int i) { return PANEL_Y0 + (i / 2) * (PANEL_H + PANEL_GAP); }

static void drawStripe(int i, uint16_t c) {
  info->fillRect(panelX(i) + 5, panelY(i) + 10, 4, PANEL_H - 20, c);
}

static void drawInfoStatic() {
  info->fillScreen(C_BG);
  info->setUTF8Print(true);
  info->setFont(u8g2_font_helvB10_tr);
  info->setTextColor(C_RIM);
  for (int i = 0; i < CELLS; i++) {
    info->fillRoundRect(panelX(i), panelY(i), PANEL_W, PANEL_H, 8, C_BAND);
    drawStripe(i, C_DIM);
    info->setCursor(panelX(i) + 18, panelY(i) + 17);
    info->print(cells[i].label);
    cells[i].last[0] = 0;
    cells[i].lastUnit[0] = 0;
    cells[i].lastBar = -2;
  }
}

static void setCell(int i, const char *text, const char *unit, uint16_t color, uint16_t stripe, int bar = -1) {
  Cell &c = cells[i];
  if (!strcmp(c.last, text) && !strcmp(c.lastUnit, unit) && c.lastColor == color && c.lastStripe == stripe &&
      c.lastBar == bar) return;
  strncpy(c.last, text, sizeof(c.last) - 1);
  c.last[sizeof(c.last) - 1] = 0;
  strncpy(c.lastUnit, unit, sizeof(c.lastUnit) - 1);
  c.lastUnit[sizeof(c.lastUnit) - 1] = 0;
  c.lastColor = color;
  c.lastStripe = stripe;
  c.lastBar = bar;

  int px = panelX(i), py = panelY(i);
  int x = px + 18, base = py + PANEL_H - 8;
  info->fillRect(px + 14, py + 21, PANEL_W - 20, PANEL_H - 25, C_BAND);   // value area only
  drawStripe(i, stripe);
  int16_t x1, y1;
  uint16_t w, h;
  info->setFont(u8g2_font_logisoso20_tr);
  info->setTextColor(color);
  info->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
  info->setCursor(x, base);
  info->print(text);
  info->setFont(u8g2_font_helvB10_tr);
  info->setTextColor(C_RIM);
  info->setCursor(x + w + 4, base);
  info->print(unit);
  if (bar >= 0) {
    int bx = px + 92, bw = PANEL_W - 92 - 10;
    info->fillRoundRect(bx, base - 9, bw, 8, 2, C_DIM);
    if (bar > 0) info->fillRoundRect(bx, base - 9, max(3, bw * bar / 100), 8, 2, color);
  }
}

static void updateInfo(const Telemetry &t, bool alive) {
  char b[8];
  static int peakC = -100;   // highest head temp since power-on
  if (!alive) {
    for (int i = 0; i < CELLS; i++) if (i != 1) setCell(i, "--", "", C_DIM, C_DIM);   // 1 = peak head, handled below
    if (peakC > -100) {
      snprintf(b, sizeof(b), "%d", peakC);
      setCell(1, b, "C", C_RIM, C_DIM);   // keep the peak visible, dimmed
    } else {
      setCell(1, "--", "", C_DIM, C_DIM);
    }
    return;
  }
  uint16_t st;
  snprintf(b, sizeof(b), "%d", t.cltC);
  st = t.cltC >= HEAD_DANGER_C ? C_RED : t.cltC >= HEAD_WARN_C ? C_ORANGE : C_GREEN;
  setCell(0, b, "C", st == C_GREEN ? C_FG : st, st);
  snprintf(b, sizeof(b), "%d", t.iatC);
  setCell(6, b, "C", C_FG, C_GREEN);
  float v = t.battMv / 1000.0f;
  snprintf(b, sizeof(b), "%.1f", v);
  st = (v < 11.5f || v > 15.0f) ? C_RED : v < 12.5f ? C_ORANGE : C_GREEN;
  setCell(7, b, "V", st == C_GREEN ? C_FG : st, st);
  snprintf(b, sizeof(b), "%u", t.mapKpa);
  setCell(3, b, "kPa", C_FG, C_GREEN);
  int tps = constrain((int)t.tpsPct, 0, 100);
  snprintf(b, sizeof(b), "%d", tps);
  setCell(2, b, "%", C_FG, C_GREEN, tps / 5 * 5);   // bar in 5% steps so it doesn't redraw on every count
  snprintf(b, sizeof(b), "%.1f", t.o2Raw / 10.0f);   // check scaling against your ini
  setCell(4, b, "", C_FG, C_GREEN);
  snprintf(b, sizeof(b), "%d", t.advanceDeg);
  setCell(5, b, "deg", C_FG, C_GREEN);
  peakC = max(peakC, (int)t.cltC);
  snprintf(b, sizeof(b), "%d", peakC);
  st = peakC >= HEAD_DANGER_C ? C_RED : peakC >= HEAD_WARN_C ? C_ORANGE : C_GREEN;
  setCell(1, b, "C", st == C_GREEN ? C_FG : st, st);
}

// ---- Main --------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_TACH_BL, OUTPUT);
  pinMode(PIN_INFO_BL, OUTPUT);
  digitalWrite(PIN_TACH_BL, HIGH);   // GC9B72 stays black unless BL is high
  digitalWrite(PIN_INFO_BL, HIGH);

  if (!tach->begin(20000000)) Serial.println("tach init failed");
#if INFO_SCREEN
  if (!info->begin(20000000)) Serial.println("info init failed");
#endif
  drawTachFace();
  drawNoData();
#if INFO_SCREEN
  drawInfoStatic();
#endif

  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(OTA_SSID, OTA_PASS, 1);   // channel 1, same as the bridge's default
  ArduinoOTA.setHostname("speeduino-dash");
  ArduinoOTA.onStart([]() { otaBusy = true; });
  ArduinoOTA.onEnd([]() { otaBusy = false; });
  ArduinoOTA.onError([](ota_error_t) { otaBusy = false; });
  ArduinoOTA.begin();
  webSetup();
  otaActive = true;

#if !SIM_LOCAL
  if (esp_now_init() == ESP_OK) esp_now_register_recv_cb(onRecv);
  else Serial.println("ESP-NOW init failed");
#endif
}

void loop() {
  if (otaActive) {
    ArduinoOTA.handle();
    dns.processNextRequest();
    web.handleClient();
    if (!otaBusy && millis() > OTA_WINDOW_MS && WiFi.softAPgetStationNum() == 0) {
      ArduinoOTA.end();
      web.stop();
      dns.stop();
      WiFi.softAPdisconnect(true);   // leaves the radio in STA mode for ESP-NOW
      otaActive = false;
    }
  }
  static uint32_t last = 0;
  if (millis() - last < 50) return;   // 20 Hz
  last = millis();

  Telemetry t;
  bool alive = getTelemetry(t);
  updateTach(t, alive);
#if INFO_SCREEN
  updateInfo(t, alive);
#endif
}
