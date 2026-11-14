#pragma once
#include <stdint.h>
#include <string.h>
#include <mbedtls/md.h>

// Firmware update of the bridge over ESP-NOW, relayed by the dash (which gets the .bin from its upload page).
// Stop-and-wait: the dash sends one message, the bridge answers it, the dash sends the next.
//   dash -> bridge: HELLO                  bridge -> dash: NONCE (random, fresh per attempt) or ACK(REFUSED)
//   dash -> bridge: BEGIN(hmac of nonce)   bridge -> dash: ACK
//   dash -> bridge: DATA(offset, bytes)    bridge -> dash: ACK(next offset expected)
//   dash -> bridge: END(size, hmac of nonce + size + SHA-256 of the image)
// The bridge only switches to the new image if that last hmac matches, so a stranger on the air can't flash it.
// BRIDGE_KEY lives in include/bridge_key.h (git-ignored, see bridge_key.example.h). Without it both ends build with the
// update feature switched off.
#if __has_include("bridge_key.h")
#include "bridge_key.h"
#define BRIDGE_UPDATE 1
#else
#define BRIDGE_UPDATE 0
#endif

namespace upd {
constexpr uint8_t MAGIC = 0x55;
enum : uint8_t { HELLO = 1, BEGIN = 2, DATA = 3, END = 4, ABORT = 5, NONCE = 0x81, ACK = 0x82 };
enum : uint8_t { OK = 0, BAD_AUTH = 1, BEGIN_FAIL = 2, WRITE_FAIL = 3, REFUSED = 4, BAD_HASH = 5, NOT_STARTED = 6 };
constexpr size_t NONCE_LEN = 16, MAC_LEN = 32, CHUNK = 192;
// Message sizes: HELLO/ABORT 2, NONCE 18, BEGIN 34, DATA 6+n, END 38, ACK 7 (status, next offset). None of the replies
// the dash receives is the size of a Telemetry packet, which is how the dash tells them apart.

#if BRIDGE_UPDATE
inline void hmac(const uint8_t *in, size_t n, uint8_t out[MAC_LEN]) {
  static const uint8_t key[] = BRIDGE_KEY;
  mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), key, sizeof(key), in, n, out);
}
inline void beginMac(const uint8_t nonce[NONCE_LEN], uint8_t out[MAC_LEN]) {
  uint8_t b[1 + NONCE_LEN] = {'B'};
  memcpy(b + 1, nonce, NONCE_LEN);
  hmac(b, sizeof(b), out);
}
inline void endMac(const uint8_t nonce[NONCE_LEN], uint32_t size, const uint8_t hash[32], uint8_t out[MAC_LEN]) {
  uint8_t b[1 + NONCE_LEN + 4 + 32] = {'E'};
  memcpy(b + 1, nonce, NONCE_LEN);
  memcpy(b + 1 + NONCE_LEN, &size, 4);
  memcpy(b + 1 + NONCE_LEN + 4, hash, 32);
  hmac(b, sizeof(b), out);
}
inline bool macEq(const uint8_t *a, const uint8_t *b) {
  uint8_t diff = 0;
  for (size_t i = 0; i < MAC_LEN; i++) diff |= a[i] ^ b[i];
  return diff == 0;
}

// Running SHA-256 of the image as it streams past.
struct Sha {
  mbedtls_md_context_t c;
  bool on = false;
  void start() {
    stop();
    mbedtls_md_init(&c);
    mbedtls_md_setup(&c, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 0);
    mbedtls_md_starts(&c);
    on = true;
  }
  void add(const uint8_t *p, size_t n) { if (on) mbedtls_md_update(&c, p, n); }
  void finish(uint8_t out[32]) { if (on) { mbedtls_md_finish(&c, out); stop(); } }
  void stop() { if (on) { mbedtls_md_free(&c); on = false; } }
};
#endif
}  // namespace upd
