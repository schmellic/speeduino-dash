#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <Arduino_GFX_Library.h>
#include <Arduino_GC9B72.h>
#include "Telemetry.h"

#ifndef SIM_LOCAL
#define SIM_LOCAL 0
#endif

// ---- Wiring (classic ESP32) -------------------------------------------
constexpr int PIN_SCK = 18, PIN_MOSI = 23, PIN_DC = 21;
constexpr int PIN_TACH_CS = 5,  PIN_TACH_RST = 22, PIN_TACH_BL = 25;
constexpr int PIN_INFO_CS = 4,  PIN_INFO_RST = 27, PIN_INFO_BL = 26;

// ---- Gauge settings ----------------------------------------------------
constexpr int RPM_MAX = 7000;
constexpr int RPM_SHIFT = 5000;     // digits turn orange
constexpr int RPM_REDLINE = 5500;   // digits turn red, red band on dial
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

// ---- Tach --------------------------------------------------------------
constexpr int CX = 180, CY = 180;

static float rpmToDeg(float rpm) {
  return 135.0f + constrain(rpm, 0, RPM_MAX) * 270.0f / RPM_MAX;
}
static void polar(float deg, float r, int &x, int &y) {
  float a = deg * DEG_TO_RAD;
  x = CX + lroundf(r * cosf(a));
  y = CY + lroundf(r * sinf(a));
}
static void thickLine(float deg, float r0, float r1, float halfW, uint16_t c) {
  int x0, y0, x1, y1, px, py;
  polar(deg, r0, x0, y0);
  polar(deg, r1, x1, y1);
  float a = (deg + 90) * DEG_TO_RAD;
  px = lroundf(halfW * cosf(a));
  py = lroundf(halfW * sinf(a));
  tach->fillTriangle(x0 - px, y0 - py, x0 + px, y0 + py, x1 + px, y1 + py, c);
  tach->fillTriangle(x0 - px, y0 - py, x1 + px, y1 + py, x1 - px, y1 - py, c);
}

static void drawTachFace() {
  tach->fillScreen(C_BG);
  tach->drawCircle(CX, CY, 178, C_DIM);
  for (float d = rpmToDeg(RPM_REDLINE); d <= rpmToDeg(RPM_MAX); d += 0.4f)
    thickLine(d, 146, 156, 1.5f, C_BAD);
  for (int rpm = 0; rpm <= RPM_MAX; rpm += 500) {
    bool major = rpm % 1000 == 0;
    thickLine(rpmToDeg(rpm), major ? 156 : 164, 174, major ? 2.5f : 1.0f, C_FG);
  }
  tach->setTextSize(3);
  tach->setTextColor(C_FG, C_BG);
  for (int k = 0; k <= RPM_MAX / 1000; k++) {
    int x, y;
    polar(rpmToDeg(k * 1000), 132, x, y);
    tach->setCursor(x - 9, y - 12);
    tach->print(k);
  }
  tach->setTextSize(2);
  tach->setTextColor(C_DIM, C_BG);
  tach->setCursor(CX - 54, CY + 118);
  tach->print("RPM x1000");
}

static void drawNeedle(float deg, uint16_t c) {
  int tx, ty, bx, by, px, py;
  polar(deg, 110, tx, ty);
  polar(deg + 180, 20, bx, by);
  float a = (deg + 90) * DEG_TO_RAD;
  px = lroundf(5 * cosf(a));
  py = lroundf(5 * sinf(a));
  tach->fillTriangle(CX + px, CY + py, CX - px, CY - py, tx, ty, c);
  tach->fillTriangle(CX + px, CY + py, CX - px, CY - py, bx, by, c);
}

static float shownRpm = 0;
static int lastNeedleDeg10 = -1;
static int lastRpmDigits = -1;
static bool tachShowsNoData = true;

static void updateTach(const Telemetry &t, bool alive) {
  tach->setTextSize(5);
  if (!alive) {
    if (!tachShowsNoData) {
      drawNeedle(rpmToDeg(shownRpm), C_BG);
      tachShowsNoData = true;
      lastRpmDigits = -1;
      lastNeedleDeg10 = -1;
    }
    tach->setTextColor(C_DIM, C_BG);
    tach->setCursor(CX - 60, CY + 55);
    tach->print("----  ");
    return;
  }
  tachShowsNoData = false;
  shownRpm += (t.rpm - shownRpm) * 0.35f;
  float deg = rpmToDeg(shownRpm);
  int deg10 = lroundf(deg * 10);
  if (deg10 != lastNeedleDeg10) {
    if (lastNeedleDeg10 >= 0) drawNeedle(lastNeedleDeg10 / 10.0f, C_BG);
    drawNeedle(deg, C_WARN);
    tach->fillCircle(CX, CY, 10, C_FG);
    lastNeedleDeg10 = deg10;
  }
  int digits = (int)(shownRpm / 10) * 10;
  if (digits != lastRpmDigits) {
    lastRpmDigits = digits;
    uint16_t c = digits >= RPM_REDLINE ? C_BAD : digits >= RPM_SHIFT ? C_WARN : C_FG;
    char buf[8];
    snprintf(buf, sizeof(buf), "%4d", digits);
    tach->setTextColor(c, C_BG);
    tach->setCursor(CX - 60, CY + 55);
    tach->print(buf);
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
  if (!info->begin(20000000)) Serial.println("info init failed");
  drawTachFace();
  drawInfoStatic();

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
  updateInfo(t, alive);
}
