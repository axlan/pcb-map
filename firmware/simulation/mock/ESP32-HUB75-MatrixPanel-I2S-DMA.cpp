#include "ESP32-HUB75-MatrixPanel-I2S-DMA.h"

#include <SFML/Graphics.hpp>  // Include SFML here for implementation
#include <iostream>

// Initialize the static member outside the class definition
sf::RenderWindow* MatrixPanel_I2S_DMA::window_ = nullptr;
sf::Texture* MatrixPanel_I2S_DMA::overlayTexture_ = nullptr;
sf::Sprite* MatrixPanel_I2S_DMA::overlaySprite_ = nullptr;
bool MatrixPanel_I2S_DMA::redraw_ = true;

#define BOARD_WIDTH_MM 240
#define BOARD_HEIGHT_MM 320
#define MATRIX_WIDTH_MM 320
#define MATRIX_HEIGHT_MM 160

#define PIXELS_PER_MM 3

#define WINDOW_WIDTH_PIXELS (BOARD_WIDTH_MM * PIXELS_PER_MM)
#define WINDOW_HEIGHT_PIXELS (BOARD_HEIGHT_MM * PIXELS_PER_MM)
#define LED_SIZE_PIXELS \
  (MATRIX_WIDTH_MM / MatrixPanel_I2S_DMA::COLS * PIXELS_PER_MM)
#define MATRIX_HEIGHT_PIXELS (MATRIX_HEIGHT_MM * PIXELS_PER_MM)

#define MATRIX_X_OFFSET_MM 42

#define MATRIX_X_OFFSET_PIXELS (MATRIX_X_OFFSET_MM * PIXELS_PER_MM)

MatrixPanel_I2S_DMA::MatrixPanel_I2S_DMA(HUB75_I2S_CFG cfg) {
  if (!window_) {
    window_ = new sf::RenderWindow(
        sf::VideoMode(WINDOW_WIDTH_PIXELS, WINDOW_HEIGHT_PIXELS),
        "PCB-MAP Matrix Simulator");
    window_->setFramerateLimit(60);

    // Load overlay image from data directory
    overlayTexture_ = new sf::Texture();
    if (overlayTexture_->loadFromFile(
            "../simulation/data/map_board_preview.png")) {
      overlaySprite_ = new sf::Sprite(*overlayTexture_);
      sf::Vector2u size = overlayTexture_->getSize();

      // Set origin to center for rotation, then position in window center
      // overlaySprite_->setOrigin(size.x / 2.0f, size.y / 2.0f);
      // overlaySprite_->setPosition((COLS * LED_SIZE_PIXELS) / 2.0f, (ROWS *
      // LED_SIZE_PIXELS) / 2.0f); overlaySprite_->setRotation(90.0f);

      std::cout << size.x << " " << size.y << std::endl;

      // Scale to fit simulation window (swapping dims due to 90deg rotation)
      float scaleX = (float)(WINDOW_WIDTH_PIXELS) / size.x;
      float scaleY = (float)(WINDOW_HEIGHT_PIXELS) / size.y;

      std::cout << scaleX << " " << scaleY << std::endl;
      std::cout << size.x * scaleX << " " << size.y * scaleY << std::endl;

      overlaySprite_->setScale(scaleX, scaleY);
      overlaySprite_->setColor(
          sf::Color(255, 255, 255, 128));  // 50% transparency
    }
  }
}

void MatrixPanel_I2S_DMA::begin() {
  printf("[MockMatrix] SFML Backend Initialized\n");
}

void MatrixPanel_I2S_DMA::setBrightness8(uint8_t b) {
  printf("[MockMatrix] Brightness set to %d\n", b);
}

void MatrixPanel_I2S_DMA::clearScreen() {
  if (!window_) return;
  window_->clear(sf::Color::Black);
  auto border = sf::RectangleShape(
      sf::Vector2f(ROWS * LED_SIZE_PIXELS,
                   COLS * LED_SIZE_PIXELS));  // Panel is rotated 90 deg
  border.setPosition(MATRIX_X_OFFSET_PIXELS, 0.0f);
  border.setFillColor(sf::Color::Transparent);
  border.setOutlineColor(sf::Color::White);
  border.setOutlineThickness(-2.0f);
  window_->draw(border);
  redraw_ = true;
}

void MatrixPanel_I2S_DMA::drawPixel(int x, int y, uint16_t color) {
  if (!window_ || x < 0 || x >= COLS || y < 0 || y >= ROWS) return;

  sf::RectangleShape led(
      sf::Vector2f(LED_SIZE_PIXELS - 2.0f, LED_SIZE_PIXELS - 2.0f));
  led.setPosition(MATRIX_X_OFFSET_PIXELS + MATRIX_HEIGHT_PIXELS -
                      (y * LED_SIZE_PIXELS + 1.0f),
                  x * LED_SIZE_PIXELS + 1.0f);  // Panel is rotated 90 deg

  // RGB565 to RGB888 conversion
  uint8_t r = ((color >> 11) & 0x1F) << 3;
  uint8_t g = ((color >> 5) & 0x3F) << 2;
  uint8_t b = (color & 0x1F) << 3;

  led.setFillColor(sf::Color(r, g, b));
  window_->draw(led);
  redraw_ = true;
}

void MatrixPanel_I2S_DMA::drawRGBBitmap(int x, int y, const uint16_t* bitmap,
                                        int w, int h) {
  for (int i = 0; i < h; ++i)
    for (int j = 0; j < w; ++j)
      drawPixel(MATRIX_X_OFFSET_PIXELS + MATRIX_HEIGHT_PIXELS - (y + j), x + i,
                bitmap[i * w + j]);  // Panel is rotated 90 deg
  redraw_ = true;
}

void MatrixPanel_I2S_DMA::update() {
  if (window_ && window_->isOpen()) {
    if (redraw_ && overlaySprite_) {
      window_->draw(*overlaySprite_);
      redraw_ = false;
    }
    window_->display();
    sf::Event event;
    while (window_->pollEvent(event)) {
      if (event.type == sf::Event::Closed) window_->close();
    }
  }
}

bool MatrixPanel_I2S_DMA::isOpen() { return window_ && window_->isOpen(); }