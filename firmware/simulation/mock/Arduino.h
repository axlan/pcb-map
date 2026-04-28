#pragma once
#include <chrono>

inline unsigned long millis() {
  static auto start = std::chrono::steady_clock::now();
  auto now = std::chrono::steady_clock::now();
  return std::chrono::duration_cast<std::chrono::milliseconds>(now - start)
      .count();
}

inline void delay(unsigned long ms) { /* No-op for sim loop */ }
