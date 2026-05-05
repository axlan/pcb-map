// This is mostly to make a clean interface for host testing

#pragma once

#include <stdint.h>

static constexpr const char* MQTT_SET_BRIGHTNESS_TOPIC =
    "pcb-map/set_brightness";
static constexpr const char* MQTT_SPRITE_DELETE_TOPIC = "pcb-map/sprite_delete";
static constexpr const char* MQTT_SPRITE_UPDATE_TOPIC = "pcb-map/sprite_update";
static constexpr const char* MQTT_SPRITES_CLEAR_TOPIC = "pcb-map/sprites_clear";
static constexpr const char* MQTT_BACKGROUND_SHOW_TOPIC =
    "pcb-map/background_show";
static constexpr const char* MQTT_BACKGROUND_HIDE_TOPIC =
    "pcb-map/background_hide";
static constexpr const char* MQTT_BACKGROUND_SET_ROW_TOPIC =
    "pcb-map/background_set_row";

class MatrixSpriteController;

class MatrixInterface {
 public:
  MatrixInterface(MatrixSpriteController* controller)
      : controller_(controller) {}

  void HandleMQTTMessage(const char* topic, uint8_t* payload,
                         unsigned int length);

 private:
  MatrixSpriteController* controller_;
};
