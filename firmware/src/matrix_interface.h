// This is mostly to make a clean interface for host testing

#pragma once

#include <stdint.h>

static constexpr const char* MQTT_SPRITE_DELETE_TOPIC = "pcb-map/sprite_delete";
static constexpr const char* MQTT_SPRITE_UPDATE_TOPIC = "pcb-map/sprite_update";
static constexpr const char* MQTT_SET_BACKGROUND_TOPIC =
    "pcb-map/set_background";
static constexpr const char* MQTT_CLEAR_BACKGROUND_TOPIC =
    "pcb-map/clear_background";

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
