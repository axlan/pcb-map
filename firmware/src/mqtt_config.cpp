#include "mqtt_config.h"

#include <ESPmDNS.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#include "esp_log.h"

static const char* TAG = "mqtt_config";

class ManagedUDP {
  WiFiUDP udp_;
  uint16_t port_ = 0;
  bool active_ = false;

 public:
  bool begin(uint16_t p) {
    port_ = p;
    udp_.stop();
    active_ = (udp_.begin(port_) == 1);
    return active_;
  }

  void stop() {
    udp_.stop();
    active_ = false;
  }

  void maintain() {
    if (port_ == 0) return;
    bool connected =
        (WiFi.status() == WL_CONNECTED) && (WiFi.localIP() != INADDR_NONE);
    if (connected && !active_) {
      begin(port_);
    } else if (!connected && active_) {
      stop();
    }
  }

  bool isValid() const { return active_ && (WiFi.status() == WL_CONNECTED); }

  WiFiUDP& get() { return udp_; }
};

static Preferences prefs_s;
static MQTTConfigCallback on_change_s;
static ManagedUDP udp_s;

void MQTTConfigManager::LoadMQTTConfig(MQTTConfig* mqtt_config) {
  prefs_s.begin(MQTT_PREF_NAMESPACE, true);

  mqtt_config->host = prefs_s.getString("host", MQTT_DEFAULT_HOST);

  mqtt_config->port = (uint16_t)prefs_s.getUInt("port", MQTT_DEFAULT_PORT);

  mqtt_config->use_tls = prefs_s.getBool("use_tls", MQTT_DEFAULT_USE_TLS);

  mqtt_config->user_name = prefs_s.getString("user_name", MQTT_DEFAULT_USER);
  mqtt_config->password = prefs_s.getString("password", MQTT_DEFAULT_PASS);

  prefs_s.end();
}

static void SaveMQTTConfig(const MQTTConfig& mqtt_config) {
  prefs_s.begin(MQTT_PREF_NAMESPACE, false);
  prefs_s.putString("host", mqtt_config.host.c_str());
  prefs_s.putUInt("port", mqtt_config.port);
  prefs_s.putBool("use_tls", mqtt_config.use_tls);
  prefs_s.putString("user_name", mqtt_config.user_name.c_str());
  prefs_s.putString("password", mqtt_config.password.c_str());
  prefs_s.end(); 
}

static void SendUDPReply(const IPAddress& ip, uint16_t port, const char* msg) {
  auto& udp = udp_s.get();
  udp.beginPacket(ip, port);
  udp.print(msg);
  udp.endPacket();
}

void ProcessUDPCommands() {
  // Example CMD: "SET_MQTT broker.example.com,1883,0,myuser,mypassword"
  static constexpr size_t BUFFER_SIZE = 256;
  char input[BUFFER_SIZE];

  auto& udp = udp_s.get();
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    IPAddress remoteIp = udp.remoteIP();
    uint16_t remotePort = udp.remotePort();
    if (packetSize >= BUFFER_SIZE) {
      ESP_LOGW(TAG, "[UDP] Command too big %d >= 256", packetSize);
      SendUDPReply(remoteIp, remotePort, "CMD_SIZE");
      return;
    }

    int len = udp.read(input, packetSize);
    if (len != packetSize) {
      ESP_LOGW(TAG, "[UDP] Read len %d != %d", packetSize, len);
      SendUDPReply(remoteIp, remotePort, "READ_ERROR");
      return;
    }
    input[packetSize] = 0;

    ESP_LOGI(TAG, "CMD from %s:%d → %s", remoteIp.toString().c_str(),
             remotePort, input);

    const char* prefix = "SET_MQTT ";
    const size_t prefixLen = 9;  // strlen("SET_MQTT ")

    // Verify prefix
    if (strncmp(input, prefix, prefixLen) != 0) {
      SendUDPReply(remoteIp, remotePort, "PARSE_ERROR");
      return;
    }

    const char* cursor = input + prefixLen;

    // Tokenize by comma
    int tokenIndex = 0;
    String tokens[5];
    String currentToken;

    for (const char* p = cursor; *p != '\0' && tokenIndex < 5; ++p) {
      if (*p == ',') {
        tokens[tokenIndex++] = currentToken;
        currentToken = "";
      } else {
        currentToken += *p;
      }
    }
    // Add last token
    if (tokenIndex < 5) {
      tokens[tokenIndex++] = currentToken;
    }

    if (tokenIndex != 5) {
      SendUDPReply(remoteIp, remotePort, "PARSE_ERROR");
      return;
    }

    // Parse and validate tokens
    MQTTConfig mqtt_config;
    mqtt_config.host = tokens[0];
    mqtt_config.port = (uint16_t)tokens[1].toInt();
    mqtt_config.use_tls = (tokens[2] == "1");
    mqtt_config.user_name = tokens[3];
    mqtt_config.password = tokens[4];

    // Save to preferences
    SaveMQTTConfig(mqtt_config);

    // Call callback if registered
    if (on_change_s) {
      on_change_s(mqtt_config);
    }

    SendUDPReply(remoteIp, remotePort, "OK");
  }
}

void MQTTConfigManager::Begin(const MQTTConfigCallback& on_change) {
  on_change_s = on_change;
  if (!on_change_s) {
    udp_s.stop();
    return;
  }
  MQTTConfig mqtt_config;
  LoadMQTTConfig(&mqtt_config);
  on_change_s(mqtt_config);
  udp_s.begin(MQTT_UDP_CMD_PORT);
  MDNS.addService("mqtt-config", "udp", MQTT_UDP_CMD_PORT);
  ESP_LOGI(TAG, "MQTT Config service registered: mqtt-config._udp.local:%u",
           MQTT_UDP_CMD_PORT);
}

void MQTTConfigManager::Set(const MQTTConfig& config) {
  SaveMQTTConfig(config);
  if (on_change_s) {
    on_change_s(config);
  }
}

void MQTTConfigManager::Update() {
  if (!on_change_s) return;
  udp_s.maintain();
  if (!udp_s.isValid()) return;
  ProcessUDPCommands();
}
