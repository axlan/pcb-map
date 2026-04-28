#pragma once

#include <PubSubClient.h>
#include <WiFiClientSecure.h>

#include <vector>

#include "mqtt_config.h"

class MQTTClientManager {
 private:
  WiFiClient wifi_client_;
  WiFiClientSecure wifi_client_secure_;
  PubSubClient* mqtt_client_;
  PubSubClient mqtt_client_secure_;
  PubSubClient mqtt_client_insecure_;
  unsigned long last_mqtt_attempt_ms_;
  static constexpr unsigned long MQTT_RETRY_INTERVAL_MS = 5000;
  std::vector<String> topics_;
  MQTTConfig config_;
  String client_name_;

  // Connection logic
  void Connect();

 public:
  MQTTClientManager(const char* client_name, const std::vector<String>& topics,
                    MQTT_CALLBACK_SIGNATURE, const MQTTConfig& config);

  // Update loop - handles reconnection and processes incoming messages
  void Update();

  // Config change handler
  void OnConfigChange(const MQTTConfig& config);

  void SetCACert(const char* root_ca);

  PubSubClient* GetClient() { return mqtt_client_; }
};
