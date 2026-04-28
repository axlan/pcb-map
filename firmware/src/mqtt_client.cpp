#include "mqtt_client.h"

#include <WiFi.h>
#include <WiFiManager.h>

#include "esp_log.h"

static const char* TAG = "mqtt_client";

MQTTClientManager::MQTTClientManager(const char* client_name,
                                     const std::vector<String>& topics,
                                     MQTT_CALLBACK_SIGNATURE,
                                     const MQTTConfig& config)
    : mqtt_client_secure_(wifi_client_secure_),
      mqtt_client_insecure_(wifi_client_),
      last_mqtt_attempt_ms_(0),
      client_name_(client_name),
      config_(config),
      topics_(topics) {
  mqtt_client_secure_.setCallback(callback);
  mqtt_client_insecure_.setCallback(callback);

  // This opens the possibility for man in the middle attacks to compromise the
  // encryption. The alternative would be to set the Root CA certificate for the
  // broker(s) being used. Handling that dynamically would be fairly memory
  // intensive. Ideally, if that mattered, it would make more sense to hardcode
  // the broker.
  wifi_client_secure_.setInsecure();

  mqtt_client_ =
      config_.use_tls ? &mqtt_client_secure_ : &mqtt_client_insecure_;
}

void MQTTClientManager::Update() {
  // Handle MQTT connection and reconnection
  if (mqtt_client_->connected()) {
    mqtt_client_
        ->loop();  // Process incoming messages and keep connection alive
  } else {
    Connect();  // Attempt to (re)connect with retry interval
  }
}

void MQTTClientManager::SetCACert(const char* root_ca) {
  wifi_client_secure_.setCACert(root_ca);
}

void MQTTClientManager::Connect() {
  // Only attempt if WiFi is connected
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  // Check if retry interval has passed
  unsigned long now = millis();
  if (now - last_mqtt_attempt_ms_ < MQTT_RETRY_INTERVAL_MS) {
    return;
  }
  last_mqtt_attempt_ms_ = now;

  // If already connected, nothing to do
  if (mqtt_client_->connected()) {
    return;
  }

  ESP_LOGI(TAG, "[MQTT] Attempting connection to %s:%d as %s",
           config_.host.c_str(), config_.port, client_name_.c_str());

  // Attempt to connect with credentials if provided
  bool connected = false;
  if (config_.user_name.length() > 0 && config_.password.length() > 0) {
    connected =
        mqtt_client_->connect(client_name_.c_str(), config_.user_name.c_str(),
                              config_.password.c_str());
  } else {
    connected = mqtt_client_->connect(client_name_.c_str());
  }

  if (connected) {
    ESP_LOGI(TAG, "[MQTT] Connected!");
    for (const auto& topic : topics_) {
      mqtt_client_->subscribe(topic.c_str());
      ESP_LOGI(TAG, "[MQTT] Subscribed to topic: %s", topic.c_str());
    }
  } else {
    ESP_LOGW(TAG, "[MQTT] Connection failed, rc=%d. Retrying in %lums",
             mqtt_client_->state(), MQTT_RETRY_INTERVAL_MS);
  }
}

void MQTTClientManager::OnConfigChange(const MQTTConfig& config) {
  ESP_LOGI(TAG, "[MQTT] Config updated: %s:%d (TLS: %s, User: %s)",
           config.host.c_str(), config.port, config.use_tls ? "yes" : "no",
           config.user_name.c_str());

  // Store new config
  config_ = config;

  // Disconnect if currently connected
  if (mqtt_client_->connected()) {
    mqtt_client_->disconnect();
  }
  mqtt_client_ =
      config_.use_tls ? &mqtt_client_secure_ : &mqtt_client_insecure_;

  // Configure client with new settings
  mqtt_client_->setServer(config.host.c_str(), config.port);

  // Force immediate reconnection attempt
  last_mqtt_attempt_ms_ = 0;
  Connect();
}
