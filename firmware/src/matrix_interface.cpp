#include "matrix_interface.h"

#include <ArduinoJson.h>
#include <esp_log.h>

#include <cstring>
#include <memory>

#include "matrix_sprite_ctrl.h"

static const char *TAG = "matrix_interface";

enum class ParseError { OK, NOT_A_NUMBER, OUT_OF_RANGE };

ParseError ParsePercent(const std::string &s, float *out) {
  size_t pos;
  try {
    *out = std::stof(s, &pos);
  } catch (const std::invalid_argument &) {
    return ParseError::NOT_A_NUMBER;  // not a number
  } catch (const std::out_of_range &) {
    return ParseError::OUT_OF_RANGE;  // too large for float
  }

  if (pos != s.size())
    return ParseError::NOT_A_NUMBER;  // trailing non-numeric characters

  if (*out < 0.0f || *out > 100.0f)
    return ParseError::OUT_OF_RANGE;  // out of range

  return ParseError::OK;
}

void MatrixInterface::HandleMQTTMessage(const char *topic, uint8_t *payload,
                                        unsigned int length) {
  if (strcmp(topic, MQTT_SPRITE_UPDATE_TOPIC) == 0) {
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
      if (!doc["offset_ms"].isNull() && !doc["offset_ms"].is<int>()) {
        ESP_LOGE(TAG, "Invalid 'offset_ms' field (must be int)");
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
      unsigned offset_ms = !doc["offset_ms"].isNull()
                               ? doc["offset_ms"].as<int>()
                               : EFFECT_PERIOD_MS / (speed * 2.0);

      ESP_LOGI(TAG, "Valid sprite update received: name='%s', x=%d, y=%d", name,
               x, y);

      controller_->AddSprite(std::unique_ptr<PixelSprite>(
          new PixelSprite(name, x, y, color, end_color, speed, offset_ms)));
    }
  } else if (strcmp(topic, MQTT_SPRITE_DELETE_TOPIC) == 0) {
    auto name = reinterpret_cast<const char *>(payload);
    ESP_LOGI(TAG, "Clearing sprite '%.*s'", length, name);
    controller_->PopSprite(name, length);
  } else if (strcmp(topic, MQTT_SET_BRIGHTNESS_TOPIC) == 0) {
    ESP_LOGI(TAG, "Setting brightness");
    float brightness = 0;
    ParseError err = ParsePercent(
        std::string(reinterpret_cast<const char *>(payload), length),
        &brightness);
    if (err == ParseError::OK) {
      // Add a small epsilon to avoid floating point errors rounding down.
      controller_->SetBrightness(brightness * 2.55001);
    } else {
      ESP_LOGI(TAG, "Brightness not a valid percentage.");
    }
  } else if (strcmp(topic, MQTT_SPRITES_CLEAR_TOPIC) == 0) {
    ESP_LOGI(TAG, "Clearing sprites");
    controller_->ClearSprites();
  } else if (strcmp(topic, MQTT_BACKGROUND_SET_ROW_TOPIC) == 0) {
    static constexpr size_t EXPECTED_MESSAGE_SIZE = PANEL_ROW_BYTES + 1;
    if (length == EXPECTED_MESSAGE_SIZE) {
      uint8_t row = payload[0];
      if (row < PANEL_RES_Y) {
        ESP_LOGI(TAG, "Setting background row %u from binary data", row);
        controller_->DrawBackgroundRow(
            row, reinterpret_cast<const Color565 *>(payload + 1));
      } else {
        ESP_LOGW(TAG, "Background row out of range. Expected 0-%u, got %u",
                 PANEL_RES_Y - 1, row);
      }
    } else {
      ESP_LOGW(
          TAG,
          "Unexpected size for background image. Expected %zu bytes, got %u",
          EXPECTED_MESSAGE_SIZE, length);
    }
  } else if (strcmp(topic, MQTT_BACKGROUND_HIDE_TOPIC) == 0) {
    ESP_LOGI(TAG, "Hide background image");
    controller_->SetBackgroundEnabled(false);
  } else if (strcmp(topic, MQTT_BACKGROUND_SHOW_TOPIC) == 0) {
    ESP_LOGI(TAG, "Show background image");
    controller_->SetBackgroundEnabled(true);
  }
}
