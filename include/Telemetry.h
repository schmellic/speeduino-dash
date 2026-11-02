#pragma once
#include <stdint.h>

// Packet sent from the bridge node (at the ECU) to the display node (at the dash).
struct __attribute__((packed)) Telemetry {
  uint16_t rpm;
  uint16_t mapKpa;
  int16_t  cltC;
  int16_t  iatC;
  uint16_t battMv;
  uint8_t  tpsPct;
  int8_t   advanceDeg;
  uint8_t  o2Raw;      // Speeduino O2 channel (AFR x10 on most setups)
  uint8_t  linkOk;     // 1 = bridge is getting valid data from the ECU
  uint8_t  seq;
};
