#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
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
constexpr int RPM_MAX = 7000;
constexpr int RPM_SHIFT = 4500;     // ring turns orange here (user)
constexpr int RPM_REDLINE = 5400;   // Beetle redline (user): digits and ring turn red here
constexpr int HEAD_WARN_C = 190, HEAD_DANGER_C = 220;
constexpr uint32_t STALE_MS = 500;

// ---- Displays (both share SCK/MOSI/DC, each has its own CS and RST) ----
Arduino_DataBus *busTach = new Arduino_ESP32SPI(PIN_DC, PIN_TACH_CS, PIN_SCK, PIN_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *tach = new Arduino_GC9B72(busTach, PIN_TACH_RST, 0, false, 360, 360);
Arduino_DataBus *busInfo = new Arduino_ESP32SPI(PIN_DC, PIN_INFO_CS, PIN_SCK, PIN_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *info = new Arduino_ILI9341(busInfo, PIN_INFO_RST, 1);   // landscape 320x240

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
// No needle and no frame buffer: the ring is 70 blocks of 100 rpm that are lit or cleared as the revs change, so nothing
// is ever erased by a thin shape. Only the blocks that change are redrawn, then the numerals go back on top.
constexpr int CX = 180, CY = 180;
constexpr int SEG_RPM = 100, SEG_N = RPM_MAX / SEG_RPM;   // 70 blocks; 100 divides the 5400 redline
constexpr int RING_IN = 126, RING_OUT = 166;              // lit blocks
constexpr int BAND_IN = 124, BAND_OUT = 168;              // dark ring behind them
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
  tach->drawCircle(CX, CY, 104, C_DISC);
  tach->drawCircle(CX, CY, 105, C_DISC);
  drawNumerals();
  tach->setFont(u8g2_font_helvB10_tr);
  tach->setTextColor(C_DIM);
  textCentered("RPM", CX, CY - 54);
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

// ---- Info screen (2 columns x 3 rows, 160x80 cells) --------------------
struct Cell { const char *label; char last[8]; uint16_t lastColor; };
static Cell cells[6] = {
  {"HEAD TEMP"}, {"INTAKE"}, {"BATTERY"}, {"MAP"}, {"AFR"}, {"ADVANCE"},
};

static void drawInfoStatic() {
  info->fillScreen(C_BG);
  info->drawFastVLine(160, 0, 240, C_DIM);
  info->drawFastHLine(0, 80, 320, C_DIM);
  info->drawFastHLine(0, 160, 320, C_DIM);
  info->setTextSize(2);
  info->setTextColor(C_DIM, C_BG);
  for (int i = 0; i < 6; i++) {
    info->setCursor((i % 2) * 160 + 10, (i / 2) * 80 + 8);
    info->print(cells[i].label);
    cells[i].last[0] = 0;
  }
}

static void setCell(int i, const char *text, uint16_t color) {
  if (!strcmp(cells[i].last, text) && cells[i].lastColor == color) return;
  strncpy(cells[i].last, text, sizeof(cells[i].last) - 1);
  cells[i].last[sizeof(cells[i].last) - 1] = 0;
  cells[i].lastColor = color;
  char buf[8];
  snprintf(buf, sizeof(buf), "%-6s", text);   // pad so old digits are overwritten
  info->setTextSize(4);
  info->setTextColor(color, C_BG);
  info->setCursor((i % 2) * 160 + 10, (i / 2) * 80 + 34);
  info->print(buf);
}

static void updateInfo(const Telemetry &t, bool alive) {
  char b[8];
  if (!alive) {
    for (int i = 0; i < 6; i++) setCell(i, "--", C_DIM);
    return;
  }
  snprintf(b, sizeof(b), "%dC", t.cltC);
  setCell(0, b, t.cltC >= HEAD_DANGER_C ? C_BAD : t.cltC >= HEAD_WARN_C ? C_WARN : C_FG);
  snprintf(b, sizeof(b), "%dC", t.iatC);
  setCell(1, b, C_FG);
  float v = t.battMv / 1000.0f;
  snprintf(b, sizeof(b), "%.1fV", v);
  setCell(2, b, (v < 11.5f || v > 15.0f) ? C_BAD : v < 12.5f ? C_WARN : C_FG);
  snprintf(b, sizeof(b), "%ukPa", t.mapKpa);
  setCell(3, b, C_FG);
  snprintf(b, sizeof(b), "%.1f", t.o2Raw / 10.0f);   // check scaling against your ini
  setCell(4, b, C_FG);
  snprintf(b, sizeof(b), "%d", t.advanceDeg);
  setCell(5, b, C_FG);
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

#if !SIM_LOCAL
  WiFi.mode(WIFI_STA);
  if (esp_now_init() == ESP_OK) esp_now_register_recv_cb(onRecv);
  else Serial.println("ESP-NOW init failed");
#endif
}

void loop() {
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
