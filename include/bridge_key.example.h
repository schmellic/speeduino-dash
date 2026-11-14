// Copy to bridge_key.h (git-ignored) and replace the 16 bytes with your own random ones, e.g.
//   python3 -c "import secrets; print(', '.join('0x%02x' % b for b in secrets.token_bytes(16)))"
// The bridge and the dash must be built with the same key. Without bridge_key.h the ESP-NOW bridge update is switched off.
#define BRIDGE_KEY { 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f }
