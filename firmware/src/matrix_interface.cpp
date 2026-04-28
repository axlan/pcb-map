#include "matrix_interface.h"

#include <ArduinoJson.h>
#include <esp_log.h>

#include <cstring>
#include <memory>

#include "matrix_sprite_ctrl.h"

static const char *TAG = "matrix_interface";

void MatrixInterface::HandleMQTTMessage(const char *topic, uint8_t *payload,
                                        unsigned int length) {
  if (strcmp(topic, MQTT_SET_BACKGROUND_TOPIC) == 0) {
    constexpr size_t expected_size =
        PANEL_RES_X * PANEL_RES_Y * sizeof(Color565);
    if (length == expected_size) {
      ESP_LOGI(TAG, "Setting background image from binary data");
      controller_->DrawBackground(reinterpret_cast<const Color565 *>(payload));
    } else {
      ESP_LOGE(TAG, "Invalid background data size. Expected %zu bytes, got %u",
               expected_size, length);
    }
  } else if (strcmp(topic, MQTT_CLEAR_BACKGROUND_TOPIC) == 0) {
    ESP_LOGI(TAG, "Clearing background image");
    controller_->ClearBackground();
  } else if (strcmp(topic, MQTT_SPRITE_UPDATE_TOPIC) == 0) {
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload, length);

    if (error) {
      ESP_LOGI(TAG, "Sprite update JSON error: '%s'", error.c_str());
    } else {
      // Validate required fields
      if (!doc["name"].is<const char *>()) {
        ESP_LOGE(TAG, "Missing or invalid 'name' field");
        return;
      }
      if (!doc["color"].is<int>()) {
        ESP_LOGE(TAG, "Missing or invalid 'color' field");
        return;
      }
      if (!doc["x"].is<int>()) {
        ESP_LOGE(TAG, "Missing or invalid 'x' field");
        return;
      }
      if (!doc["y"].is<int>()) {
        ESP_LOGE(TAG, "Missing or invalid 'y' field");
        return;
      }

      // Validate range constraints
      int x = doc["x"];
      int y = doc["y"];
      if (x < 0 || x >= 64) {
        ESP_LOGE(TAG, "Invalid 'x' value: %d (must be 0-63)", x);
        return;
      }
      if (y < 0 || y >= 32) {
        ESP_LOGE(TAG, "Invalid 'y' value: %d (must be 0-31)", y);
        return;
      }

      // Validate optional fields if present
      if (!doc["end_color"].isNull() && !doc["end_color"].is<int>()) {
        ESP_LOGE(TAG, "Invalid 'end_color' field (must be int)");
        return;
      }
      if (!doc["speed"].isNull() && !doc["speed"].is<float>()) {
        ESP_LOGE(TAG, "Invalid 'speed' field (must be float)");
        return;
      }

      const char *name = doc["name"].as<const char *>();
      Color565 color = static_cast<Color565>(doc["color"].as<int>());
      // Default to pulsing to black
      Color565 end_color =
          !doc["end_color"].isNull()
              ? static_cast<Color565>(doc["end_color"].as<int>())
              : 0;
      float speed = !doc["speed"].isNull() ? doc["speed"].as<float>() : 1.0f;

      // When speed is 1.0, sync the occurrence of the end color with the
      // transition between sprites.
      unsigned offset_ms = EFFECT_PERIOD_MS / (speed * 2.0);

      ESP_LOGI(TAG, "Valid sprite update received: name='%s', x=%d, y=%d", name,
               x, y);

      controller_->AddSprite(std::unique_ptr<PixelSprite>(
          new PixelSprite(name, x, y, color, end_color, speed, offset_ms)));
    }
  } else if (strcmp(topic, MQTT_SPRITE_DELETE_TOPIC) == 0) {
    auto name = reinterpret_cast<const char *>(payload);
    ESP_LOGI(TAG, "Clearing sprite '%.*s'", length, name);
    controller_->PopSprite(name, length);
  }
}
