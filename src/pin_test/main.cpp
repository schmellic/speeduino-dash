// Wiring check for the round tach: drives each signal pin HIGH for 4 s in turn (others LOW) so a multimeter on the screen's
// pin (against GND) can confirm the wire is continuous. The on-board LED (GPIO2) blinks N times before pin N.
//   1: RST (22)  2: CS (5)  3: DC (21)  4: SCL (18)  5: SDA (23)  6: BL (25)
#include <Arduino.h>

constexpr int PINS[] = {22, 5, 21, 18, 23, 25};
constexpr const char *NAMES[] = {"RST", "CS", "DC", "SCL", "SDA", "BL"};
constexpr int N = 6, PIN_LED = 2;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  for (int p : PINS) { pinMode(p, OUTPUT); digitalWrite(p, LOW); }
}

void loop() {
  for (int i = 0; i < N; i++) {
    for (int p : PINS) digitalWrite(p, LOW);
    for (int b = 0; b <= i; b++) { digitalWrite(PIN_LED, HIGH); delay(200); digitalWrite(PIN_LED, LOW); delay(200); }
    digitalWrite(PINS[i], HIGH);
    Serial.printf("%d: %s (GPIO%d) HIGH\n", i + 1, NAMES[i], PINS[i]);
    delay(4000);
  }
}
