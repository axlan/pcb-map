// pio run -t upload --upload-port pcb-map.local

#include <Arduino.h>
#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <WiFiManager.h>

#include "esp_log.h"

static const char* TAG = "main";

#include "matrix_interface.h"
#include "matrix_sprite_ctrl.h"
#include "mqtt_client.h"
#include "mqtt_config.h"

static constexpr const char* MDNS_HOSTNAME = "pcb-map";

static constexpr const char* ADHOC_AP = "pcb-map-ap";

// Topic constants
static constexpr const char* MQTT_CLIENT_NAME = "pcb-map";
static constexpr const char* MQTT_CLEAR_WIFI_TOPIC = "pcb-map/clear_wifi";
static constexpr const char* MQTT_PING_TOPIC = "pcb-map/ping";
static constexpr const char* MQTT_PONG_TOPIC = "pcb-map/pong";
static constexpr const char* MQTT_STATS_TOPIC = "pcb-map/stats";

static const unsigned long STATS_PUBLISH_INTERVAL = 10000;  // 10 seconds
static const float ROLLING_AVG_ALPHA =
    0.1f;  // Exponential moving average factor

// Stats calculation state - Internal state for rolling averages and timing
struct StatsState {
  float loop_time_rolling_avg = 0.0f;
  unsigned long loop_cycle_start_time = 0;
  unsigned long last_stats_publish_time = 0;
  float loop_time_worst = 0.0f;
  uint32_t commands_handled = 0;
};

static StatsState current_stats;

// clang-format off
// Root CA Cert for *.s1.eu.hivemq.cloud (https://letsencrypt.org/certs/isrgrootx1.pem)
// #define MQTT_BROKER_CA_CERT "-----BEGIN CERTIFICATE-----\nMIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw\nTzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh\ncmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4\nWhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu\nZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY\nMTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc\nh77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+\n0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U\nA5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW\nT8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH\nB5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC\nB5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv\nKBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn\nOlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn\njh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw\nqHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI\nrU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV\nHRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq\nhkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL\nubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ\n3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK\nNFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5\nORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur\nTkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC\njNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc\noyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq\n4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA\nmRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d\nemyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=\n-----END CERTIFICATE-----"
// clang-format on

static void HandleMQTTMessage(const char* topic, byte* payload, unsigned int length);

MQTTClientManager mqtt_manager(MQTT_CLIENT_NAME,
                               {MQTT_CLEAR_WIFI_TOPIC, MQTT_PING_TOPIC,
                                MQTT_SPRITE_DELETE_TOPIC,
                                MQTT_SPRITE_UPDATE_TOPIC,
                                MQTT_SPRITES_CLEAR_TOPIC,
                                MQTT_BACKGROUND_SET_ROW_TOPIC,
                                MQTT_BACKGROUND_SHOW_TOPIC,
                                MQTT_BACKGROUND_HIDE_TOPIC},
                               HandleMQTTMessage, MQTTConfig{});

MatrixSpriteController sprite_ctrl;
MatrixInterface matrix_interface(&sprite_ctrl);

static void HandleMQTTMessage(const char* topic, byte* payload,
                              unsigned int length) {
  ESP_LOGI(TAG, "[MQTT] Message received on topic: %s", topic);

  if (strcmp(topic, MQTT_CLEAR_WIFI_TOPIC) == 0) {
    ESP_LOGI(TAG, "[MQTT] Clearing WiFi credentials and restarting...");

    // Clear saved WiFi credentials
    WiFiManager wm;
    wm.resetSettings();

    delay(1000);
    ESP.restart();
  } else if (strcmp(topic, MQTT_PING_TOPIC) == 0) {
    ESP_LOGI(TAG, "[MQTT] Responding to ping...");

    mqtt_manager.GetClient()->publish(MQTT_PONG_TOPIC, "pong");
  } else {
    matrix_interface.HandleMQTTMessage(topic, payload, length);
  }
  current_stats.commands_handled++;
}

void setupOTA() {
  ArduinoOTA.setHostname(MDNS_HOSTNAME);

  ArduinoOTA.onStart([]() {
    String type =
        (ArduinoOTA.getCommand() == U_FLASH) ? "sketch" : "filesystem";
    ESP_LOGI(TAG, "OTA Update starting: %s", type.c_str());
  });

  ArduinoOTA.onEnd([]() { ESP_LOGI(TAG, "OTA Update completed!"); });

  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    ESP_LOGI(TAG, "OTA Progress: %u%%", (progress / (total / 100)));
  });

  ArduinoOTA.onError([](ota_error_t error) {
    if (error == OTA_AUTH_ERROR)
      ESP_LOGE(TAG, "OTA Error [%u]: Authentication failed", error);
    else if (error == OTA_BEGIN_ERROR)
      ESP_LOGE(TAG, "OTA Error [%u]: Begin failed", error);
    else if (error == OTA_CONNECT_ERROR)
      ESP_LOGE(TAG, "OTA Error [%u]: Connect failed", error);
    else if (error == OTA_RECEIVE_ERROR)
      ESP_LOGE(TAG, "OTA Error [%u]: Receive failed", error);
    else if (error == OTA_END_ERROR)
      ESP_LOGE(TAG, "OTA Error [%u]: End failed", error);
  });

  ArduinoOTA.begin();
}

void RunWifiManager() {
  // WiFiManager, Local initialization. Once its business is done, there is no
  // need to keep it around
  WiFiManager wm;

  // Automatically connect using saved credentials,
  // if connection fails, it starts an access point with the specified name (
  // "AutoConnectAP"), if empty will auto generate SSID, if password is blank it
  // will be anonymous AP (wm.autoConnect()) then goes into a blocking loop
  // awaiting configuration and will return success result
  bool connected = wm.autoConnect(ADHOC_AP);
  if (!connected) {
    ESP_LOGE(TAG, "Failed to connect");
    ESP.restart();
  }
}

void setup() {
  Serial.begin(115200);

  sprite_ctrl.Init();

  RunWifiManager();

#ifdef MQTT_BROKER_CA_CERT
  mqtt_manager.SetCACert(MQTT_BROKER_CA_CERT);
#endif

  MDNS.begin(MDNS_HOSTNAME);
  setupOTA();
  ESP_LOGI(TAG, "OTA Ready!");
  MQTTConfigManager::Begin(
      [&](const MQTTConfig& config) { mqtt_manager.OnConfigChange(config); });

  current_stats.last_stats_publish_time = millis();
  current_stats.loop_cycle_start_time = millis();

  // sprite_ctrl.AddSprite(SpritePtr(new PixelSprite("test",16,16,0xF800)));
}

void UpdateStats(float loop_time_ms) {
  // Update rolling average (exponential moving average)
  if (current_stats.loop_time_rolling_avg == 0.0f) {
    current_stats.loop_time_rolling_avg = loop_time_ms;
  } else {
    current_stats.loop_time_rolling_avg =
        (ROLLING_AVG_ALPHA * loop_time_ms) +
        ((1.0f - ROLLING_AVG_ALPHA) * current_stats.loop_time_rolling_avg);
  }

  // Update worst time
  if (loop_time_ms > current_stats.loop_time_worst) {
    current_stats.loop_time_worst = loop_time_ms;
  }

  // Update current stats
  auto uptime = millis() / 1000;
  auto heap_free = ESP.getFreeHeap();

  // Publish stats every 10 seconds
  if (millis() - current_stats.last_stats_publish_time >=
      STATS_PUBLISH_INTERVAL) {
    // Build JSON stats
    char json_buffer[256];
    snprintf(json_buffer, sizeof(json_buffer),
             "{\"uptime\":%lu,\"heap_free\":%u,\"loop_time_mean_ms\":%.2f,"
             "\"loop_time_worst_ms\":%.2f,\"commands_handled\":%u}",
             uptime, heap_free, current_stats.loop_time_rolling_avg,
             current_stats.loop_time_worst, current_stats.commands_handled);

    ESP_LOGI(TAG, "[Stats] %s", json_buffer);
    mqtt_manager.GetClient()->publish(MQTT_STATS_TOPIC, json_buffer);
    current_stats.loop_time_worst = 0;
    current_stats.last_stats_publish_time = millis();
  }
}

void loop() {
  unsigned long loop_start = millis();

  ArduinoOTA.handle();

  // Update MQTT client (handles connection, reconnection, and config updates)
  MQTTConfigManager::Update();
  mqtt_manager.Update();

  sprite_ctrl.Draw();

  // Calculate loop execution time
  unsigned long loop_end = millis();
  float loop_time_ms = static_cast<float>(loop_end - loop_start);
  UpdateStats(loop_time_ms);
}
