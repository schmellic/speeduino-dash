// GC9B72 bring-up: tries several bus configurations in turn, announced by blinking the on-board LED (GPIO2) N times
// before config N, then fills red/green/blue for 4 s each. Pins match src/dash/main.cpp.
//   1: hardware SPI 1 MHz   2: hardware SPI 4 MHz   3: hardware SPI 10 MHz   4: software (bit-banged) SPI
#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <Arduino_GC9B72.h>

constexpr int PIN_SCK = 18, PIN_MOSI = 23, PIN_DC = 21;
constexpr int PIN_TACH_CS = 5, PIN_TACH_RST = 22, PIN_TACH_BL = 25, PIN_LED = 2;

static void blink(int n) {
  for (int i = 0; i < n; i++) {
    digitalWrite(PIN_LED, HIGH); delay(250);
    digitalWrite(PIN_LED, LOW);  delay(250);
  }
  delay(1000);
}

static void tryConfig(int n) {
  Arduino_DataBus *bus;
  uint32_t hz = n == 1 ? 1000000 : n == 2 ? 4000000 : 10000000;
  if (n == 4) bus = new Arduino_SWSPI(PIN_DC, PIN_TACH_CS, PIN_SCK, PIN_MOSI, GFX_NOT_DEFINED);
  else        bus = new Arduino_ESP32SPI(PIN_DC, PIN_TACH_CS, PIN_SCK, PIN_MOSI, GFX_NOT_DEFINED);
  Arduino_GFX *gfx = new Arduino_GC9B72(bus, PIN_TACH_RST, 0, false, 360, 360);
  blink(n);
  bool ok = gfx->begin(n == 4 ? GFX_NOT_DEFINED : hz);
  Serial.printf("config %d begin -> %s\n", n, ok ? "ok" : "FAILED");
  gfx->fillScreen(RGB565_RED);   delay(4000);
  gfx->fillScreen(RGB565_GREEN); delay(4000);
  gfx->fillScreen(RGB565_BLUE);  delay(4000);
  delete gfx;
  delete bus;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_TACH_BL, OUTPUT);
  digitalWrite(PIN_TACH_BL, HIGH);
  delay(500);
}

void loop() {
  for (int n = 1; n <= 4; n++) tryConfig(n);
}
