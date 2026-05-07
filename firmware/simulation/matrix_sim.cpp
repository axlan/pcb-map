// mosquitto_pub -h bee.internal -t pcb-map/sprite_update -m '{"name":"test_sprite1","x":10,"y":5,"color":63488, "end_color": 32768,"speed":2}'
// mosquitto_pub -h bee.internal -t pcb-map/sprite_update -m '{"name":"test_sprite2","x":10,"y":5,"color":31, "end_color": 10,"speed":2}'
// mosquitto_pub -h bee.internal -t pcb-map/sprite_update -m '{"name":"test_sprite3","x":15,"y":15,"color":3168,"speed":0.5, "end_color": 63488}'

#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <mqtt/client.h>

#include <chrono>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include "matrix_interface.h"
#include "matrix_sprite_ctrl.h"

const std::string SERVER_ADDRESS = "tcp://localhost:1883";
const std::string CLIENT_ID = "blocking-subscriber";
const int QOS = 1;

std::vector<std::string> topics = {
    MQTT_SPRITE_DELETE_TOPIC,   MQTT_SPRITE_UPDATE_TOPIC,
    MQTT_SPRITES_CLEAR_TOPIC,   MQTT_BACKGROUND_SET_ROW_TOPIC,
    MQTT_BACKGROUND_SHOW_TOPIC, MQTT_BACKGROUND_HIDE_TOPIC};

MatrixSpriteController controller;
MatrixInterface interface(&controller);

// Callback class to handle incoming messages and connection events
class callback : public virtual mqtt::callback {
public:
    void connected(const std::string& cause) override {
        std::cout << "[connected] " << cause << "\n";
    }

    void connection_lost(const std::string& cause) override {
    std::cerr << "[connection lost] "
              << (cause.empty() ? "unknown reason" : cause) << "\n";
    }

    void message_arrived(mqtt::const_message_ptr msg) override {
        std::cout << "[message]\n"
              << "  topic:   " << msg->get_topic() << "\n"
              << "  len:     " << msg->get_payload().size() << "\n";
        auto mutable_payload = reinterpret_cast<uint8_t*>(
            const_cast<char*>(msg->get_payload().data()));
        interface.HandleMQTTMessage(msg->get_topic().c_str(), mutable_payload,
                                    msg->get_payload().size());
    }

    void delivery_complete(mqtt::delivery_token_ptr token) override {
        // Only relevant when publishing; safe to leave empty for subscribers
    }
};

int main() {
    mqtt::client client(SERVER_ADDRESS, CLIENT_ID);

    callback cb;
    client.set_callback(cb);

    mqtt::ssl_options sslOpts;
  sslOpts.set_verify(false);  // Don't verify broker certificate

    // Connection options
    mqtt::connect_options connOpts;
    connOpts.set_keep_alive_interval(20);
    connOpts.set_clean_session(true);
    connOpts.set_ssl(sslOpts);

    try {
        std::cout << "Connecting to " << SERVER_ADDRESS << "...\n";
        client.connect(connOpts);

        for (const auto& topic : topics) {
            std::cout << "Subscribing to topic: " << topic << "\n";
            client.subscribe(topic, QOS);
        }

  } catch (const mqtt::exception& e) {
        std::cerr << "MQTT error: " << e.what() << "\n";
        return 1;
    }

    controller.Init();
    
    std::cout << "Starting Matrix SFML Simulation..." << std::endl;
    
    while (MatrixPanel_I2S_DMA::isOpen()) {
        controller.Draw();
        MatrixPanel_I2S_DMA::update();

    std::this_thread::sleep_for(std::chrono::milliseconds(100));  // ~10 FPS
    }

    for (const auto& topic : topics) {
        client.unsubscribe(topic);
    }
    client.disconnect();
    std::cout << "Disconnected.\n";

    std::cout << "Simulation Complete." << std::endl;
    return 0;
}