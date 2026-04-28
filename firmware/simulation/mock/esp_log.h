#pragma once

// Stand-in macros for non-Espressif platforms
#include <cstdio>

#define ESP_LOGE(tag, format, ...) \
  fprintf(stderr, "[%s] ERROR: " format "\n", tag, ##__VA_ARGS__)
#define ESP_LOGW(tag, format, ...) \
  printf("[%s] WARN: " format "\n", tag, ##__VA_ARGS__)
#define ESP_LOGI(tag, format, ...) \
  printf("[%s] INFO: " format "\n", tag, ##__VA_ARGS__)
#define ESP_LOGD(tag, format, ...) \
  printf("[%s] DEBUG: " format "\n", tag, ##__VA_ARGS__)
#define ESP_LOGV(tag, format, ...) \
  printf("[%s] VERBOSE: " format "\n", tag, ##__VA_ARGS__)

#define ESP_EARLY_LOGE(tag, format, ...) \
  fprintf(stderr, "[%s] ERROR: " format "\n", tag, ##__VA_ARGS__)
#define ESP_EARLY_LOGW(tag, format, ...) \
  printf("[%s] WARN: " format "\n", tag, ##__VA_ARGS__)
#define ESP_EARLY_LOGI(tag, format, ...) \
  printf("[%s] INFO: " format "\n", tag, ##__VA_ARGS__)
#define ESP_EARLY_LOGD(tag, format, ...) \
  printf("[%s] DEBUG: " format "\n", tag, ##__VA_ARGS__)
#define ESP_EARLY_LOGV(tag, format, ...) \
  printf("[%s] VERBOSE: " format "\n", tag, ##__VA_ARGS__)
