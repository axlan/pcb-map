#pragma once

#include <Arduino.h>
#include <stdint.h>

#include <functional>

static constexpr uint16_t MQTT_UDP_CMD_PORT = 5432;

static constexpr const char* MQTT_PREF_NAMESPACE = "mqtt";

static constexpr const char* MQTT_DEFAULT_HOST = "bee.internal";
// 8883 for TLS encrypted
static constexpr uint16_t MQTT_DEFAULT_PORT = 1883;
static constexpr bool MQTT_DEFAULT_USE_TLS = false;
static constexpr bool MQTT_DEFAULT_USE_LOGIN = false;
static constexpr const char* MQTT_DEFAULT_USER = "";
static constexpr const char* MQTT_DEFAULT_PASS = "";

struct MQTTConfig {
  String host;
  uint16_t port = 0;
  bool use_tls = false;
  String user_name;
  String password;
};

using MQTTConfigCallback = std::function<void(const MQTTConfig&)>;

class MQTTConfigManager {
 public:
  static void LoadMQTTConfig(MQTTConfig* mqtt_config);
  static void Begin(const MQTTConfigCallback& on_change);
  static void Set(const MQTTConfig& config);
  static void Update();
};
